# MODULE: test_spend_ledger.py - BMN Epic 90.4: one reservation ledger keeps the go's money cap at every paid launch; 96.2: and counts the go's extra repair rounds
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "dev-auto" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_needs  # noqa: E402
import spend_ledger  # noqa: E402
sys.path.insert(0, str(REPO / "tests"))
import test_run_needs  # noqa: E402  (its plan fixture)

LEDGER = REPO / "tests" / "ledger_without_floor.py"  # the floor and step-back have their own tests


def go(commit: str, cap: float | None, date: str = "2026-10-23", rounds: int = 0) -> dict:
    return {"state": "GO", "plan_root": "/plans/fixture", "go_date": date, "go_commit": commit,
            "approval_source": "card 2026-10-23T09:00Z: 'Go'", "approved_text": "sha256:" + "a" * 64,
            "parsed": {"rounds": rounds, "deferrable": [], "money_cap": cap, "named_actions": None}, "stories": ["7.1", "7.2", "7.3"]}


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mock_plan = self.root / "plan-standin"
        self.mock_plan.mkdir()
        for name in ("other", "direct"):
            (self.mock_plan / name).mkdir()
        self.assertNotEqual(subprocess.run(["git", "-C", str(self.mock_plan), "rev-parse", "--show-toplevel"], capture_output=True).returncode, 0)
        # A stand-in `bmn` resolves every project to the plan a test wrote last (status.json); run_needs reads it for real.
        (self.root / "bin").mkdir()
        (self.root / "bin" / "bmn").write_text(f"#!/bin/sh\ncat '{self.root / 'status.json'}'\n")
        (self.root / "bin" / "bmn").chmod(0o755)
        patcher = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "state"), "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)
        floor = mock.patch.object(spend_ledger, "ROUND_FLOOR", 0)
        floor.start()
        self.addCleanup(floor.stop)
        self.job = self.root / "job.sh"
        self.marker = self.root / "markers"
        self.job.write_text(f'echo "$1" >> {self.marker}\n')

    def open(self, needs: dict, *extra: str) -> tuple[int, str]:
        needs = dict(needs)
        if needs.get("plan_root") == "/plans/fixture":
            needs["plan_root"] = str(self.mock_plan)
        out = io.StringIO()
        with mock.patch.object(run_needs, "run_needs", return_value=needs), contextlib.redirect_stdout(out):
            code = spend_ledger.main(["open", "--epic", "7", "--project", str(self.root / "project"), *extra])
        return code, out.getvalue()

    def open_epic(self, epic: str, needs: dict) -> str:
        needs = dict(needs)
        if needs.get("plan_root") == "/plans/fixture":
            needs["plan_root"] = str(self.mock_plan)
        out = io.StringIO()
        with mock.patch.object(run_needs, "run_needs", return_value=needs), contextlib.redirect_stdout(out):
            self.assertEqual(spend_ledger.main(["open", "--epic", epic, "--project", str(self.root / "project")]), 0)
        return out.getvalue().split()[1].rstrip(":")

    def budget(self, needs: dict) -> str:
        code, out = self.open(needs)
        self.assertEqual(code, 0, out)
        return out.split()[1].rstrip(":")

    def launch(self, budget: str, job: str, maximum: str | None, *, wait: bool = True) -> subprocess.CompletedProcess | subprocess.Popen:
        argv = [sys.executable, str(LEDGER), "launch", "--budget", budget, "--job", job, "--direct"]
        argv += ["--max", maximum] if maximum is not None else []
        argv += ["--", str(self.job), job]
        if not wait:
            return subprocess.Popen(argv, stdout=subprocess.PIPE, text=True, env=os.environ.copy())
        return subprocess.run(argv, capture_output=True, text=True, env=os.environ.copy())

    def markers(self) -> list[str]:
        for _ in range(50):  # the job runs detached; give it a moment to write
            if self.marker.exists():
                break
            time.sleep(0.02)
        time.sleep(0.1)
        return self.marker.read_text().split() if self.marker.exists() else []

    def ledger(self, budget: str) -> dict:
        return json.loads((self.root / "state" / "dev-auto" / "budgets" / f"{budget}.json").read_text())

    def test_one_ledger_per_plan_and_epic_outside_the_worktree_and_a_none_cap_refuses(self) -> None:
        budget = self.budget(go("a" * 40, None))
        self.assertRegex(budget, r"^[0-9a-f]{16}-epic-7$")
        self.assertEqual(self.budget(go("a" * 40, None)), budget)  # a resume or new lead opens the same one
        done = self.launch(budget, "review-1", "1")
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED", done.stdout)
        self.assertEqual(self.markers(), [])

    def test_under_the_cap_it_reserves_then_starts_and_a_retry_returns_the_first_answer(self) -> None:
        _, budget = self.real_budget(10.0)
        first = self.launch(budget, "review-1", "6")
        self.assertEqual(first.returncode, 0, first.stdout)
        self.assertTrue(first.stdout.startswith("STARTED"))
        again = self.launch(budget, "review-1", "6")
        self.assertEqual(again.returncode, 0)
        self.assertIn("nothing started again", again.stdout)
        over = self.launch(budget, "review-2", "5")  # 6 outstanding + 5 > 10
        self.assertEqual(over.returncode, 1)
        self.assertEqual(self.launch(budget, "review-2", "4").returncode, 1)  # a refused job id keeps its answer
        self.assertEqual(self.launch(budget, "review-3", "4").returncode, 0)  # 6 + 4 = 10 fits exactly
        self.assertEqual(sorted(self.markers()), ["review-1", "review-3"])

    def test_an_invalid_or_missing_maximum_starts_nothing(self) -> None:
        budget = self.budget(go("a" * 40, 10.0))
        for maximum in ("-1", "0", "abc", "nan", "inf", None):
            done = self.launch(budget, f"job-{maximum}", maximum)
            self.assertEqual(done.returncode, 2, (maximum, done.stdout))
        self.assertEqual(self.markers(), [])
        self.assertEqual(self.ledger(budget)["jobs"], {})

    def test_two_launches_for_the_remainder_start_exactly_one(self) -> None:
        _, budget = self.real_budget(10.0)
        opened = self.ledger(budget)
        for round_ in range(5):
            self.marker.unlink(missing_ok=True)
            spend_ledger_path = self.root / "state" / "dev-auto" / "budgets" / f"{budget}.json"
            spend_ledger_path.write_text(json.dumps({**opened, "jobs": {}}))
            runs = [self.launch(budget, f"race-{round_}-{n}", "6", wait=False) for n in range(2)]
            outputs = [run.communicate()[0] for run in runs]
            self.assertEqual(sorted(run.returncode for run in runs), [0, 1], outputs)
            self.assertEqual(len(self.markers()), 1)

    def test_settle_release_and_unknown_never_reset_the_total(self) -> None:
        _, budget = self.real_budget(10.0)
        self.assertEqual(self.launch(budget, "a", "4").returncode, 0)
        self.assertEqual(self.launch(budget, "b", "4").returncode, 0)
        self.assertEqual(spend_ledger.main(["settle", "--budget", budget, "--job", "a", "--spent", "3"]), 0)
        self.assertEqual(spend_ledger.main(["settle", "--budget", budget, "--job", "b", "--unknown"]), 0)
        # settled 3 + unknown 4 kept: 3 more fits, 4 does not
        self.assertEqual(self.launch(budget, "c", "4").returncode, 1)
        self.assertEqual(self.launch(budget, "d", "3").returncode, 0)
        self.assertEqual(spend_ledger.main(["release", "--budget", budget, "--job", "d"]), 0)
        self.assertEqual(spend_ledger.main(["settle", "--budget", budget, "--job", "a", "--spent", "0"]), 0)  # closed stays closed
        self.assertEqual(spend_ledger.totals(self.ledger(budget)), (3.0, 4.0))
        self.assertEqual(spend_ledger.main(["release", "--budget", budget, "--job", "never"]), 1)

    def test_a_reapproval_carries_consumption_and_only_a_go_adds_money(self) -> None:
        plan, budget = self.real_budget(10.0)
        self.assertEqual(self.launch(budget, "a", "6").returncode, 0)
        spend_ledger.main(["settle", "--budget", budget, "--job", "a", "--spent", "6"])
        plan.write("epic-7: in-progress # go 2026-10-23")
        plan.write("epic-7: ready # go 2026-10-25", self.epic_text(0, 12), commit=self.go_message(self.epic_text(0, 12), "2026-10-25"))
        self.assertEqual(self.open_plan(plan)[2], budget)
        self.assertEqual(self.launch(budget, "b", "7").returncode, 1)  # 6 + 7 > 12
        self.assertEqual(self.launch(budget, "c", "6").returncode, 0)  # 6 + 6 = 12
        self.assertEqual([g["cap"] for g in self.ledger(budget)["gos"]], [10.0, 12.0])
        code, out = self.open(go("b" * 40, 12.0), "--cap", "100", "--source", "I said so")
        self.assertEqual((code, out.split(":")[0]), (1, "REFUSED"))

    def test_a_systemd_launch_records_the_bare_unit_name(self) -> None:
        budget = self.budget(go("a" * 40, 10.0))
        self.enterContext(mock.patch.object(spend_ledger, "go_now", return_value=("stands", "")))  # its plan is a stand-in
        said = subprocess.CompletedProcess([], 0, "", "Running as unit: run-p1-i2.service; invocation ID: 0123abcd\n")
        with mock.patch.object(spend_ledger.subprocess, "run", return_value=said), contextlib.redirect_stdout(io.StringIO()):
            code = spend_ledger.main(["launch", "--budget", budget, "--job", "unit", "--max", "1", "--", str(self.job), "unit"])
        self.assertEqual(code, 0)
        self.assertEqual(self.ledger(budget)["jobs"]["unit"]["unit"], "run-p1-i2.service")

    def test_a_go_older_than_the_recorded_one_is_refused_and_the_cap_stays(self) -> None:
        budget = self.budget(go("b" * 40, 1.0, "2026-10-25"))
        with mock.patch.object(spend_ledger, "go_follows", return_value=False):
            code, out = self.open(go("a" * 40, 10.0, "2026-10-20"))  # read from a stale checkout
        self.assertEqual((code, out.split(":")[0]), (1, "REFUSED"))
        self.assertEqual([g["cap"] for g in self.ledger(budget)["gos"]], [1.0])
        self.assertEqual(self.launch(budget, "a", "2").returncode, 1)

    def test_one_ledger_for_an_epic_however_spelled_and_from_every_linked_worktree(self) -> None:
        self.assertEqual(self.budget(go("a" * 40, 5.0)), self.open_epic("007", go("a" * 40, 5.0)))
        repo = self.root / "repo"
        run = lambda *argv, cwd=repo: subprocess.run(["git", *argv], cwd=cwd, check=True, capture_output=True)
        (repo / "plan").mkdir(parents=True)
        run("init", "-q", cwd=self.root / "repo")
        (repo / "plan" / "status.yaml").write_text("x\n")
        run("add", ".")
        run("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "plan")
        run("worktree", "add", "-q", str(self.root / "other"))
        self.assertEqual(spend_ledger.plan_identity(str(repo / "plan")), spend_ledger.plan_identity(str(self.root / "other" / "plan")))
        self.assertNotEqual(spend_ledger.plan_identity(str(repo / "plan")), spend_ledger.plan_identity(str(repo)))

    def test_a_launch_whose_acknowledgement_timed_out_keeps_its_reservation(self) -> None:
        _, budget = self.real_budget(10.0)
        lost = subprocess.TimeoutExpired(["systemd-run"], 60)
        with mock.patch.object(spend_ledger.subprocess, "run", side_effect=lost), mock.patch.object(spend_ledger, "go_now", return_value=("stands", "")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = spend_ledger.main(["launch", "--budget", budget, "--job", "a", "--max", "8", "--", str(self.job), "a"])
        self.assertEqual((code, out.getvalue().split(":")[0]), (1, "UNKNOWN"))
        self.assertEqual(spend_ledger.totals(self.ledger(budget)), (0.0, 8.0))
        again = self.launch(budget, "a", "8")  # a retry answers as first and starts nothing
        self.assertEqual(again.returncode, 1)
        self.assertIn("UNKNOWN", again.stdout)
        self.assertEqual(self.launch(budget, "b", "8").returncode, 1)  # the money stays reserved
        self.assertEqual(spend_ledger.main(["release", "--budget", budget, "--job", "a"]), 0)  # once he knows it never ran
        self.assertEqual(self.launch(budget, "c", "8").returncode, 0)

    def test_an_owner_stated_cap_only_where_no_go_or_cap_exists(self) -> None:
        none = {"state": "NO_GO_RECORD", "plan_root": str(self.mock_plan / "other"), "reason": "no go"}
        code, out = self.open(none, "--cap", "5", "--source", "owner 2026-10-23: up to $5")
        self.assertEqual(code, 0, out)
        budget = out.split()[1].rstrip(":")
        self.assertEqual(self.launch(budget, "a", "5").returncode, 0)
        self.assertEqual(self.open(none, "--cap", "50", "--source", "more")[0], 1)
        self.assertEqual(self.open(none, "--cap", "5")[0], 2)  # no source


    def test_direct_owner_reapproval_preserves_unknown_holds_and_used_rounds(self) -> None:
        needs = {"state": "NO_GO_RECORD", "plan_root": str(self.mock_plan / "direct"), "reason": "legacy plan"}
        code, out = self.open(needs, "--cap", "30", "--source", "owner: $30")
        self.assertEqual(code, 0, out)
        budget = out.split()[1].rstrip(":")
        with (ledger := spend_ledger.Ledger(budget)) as data:
            data["jobs"]["unknown"] = {"state": "unknown", "max": 25.0}
            data["rounds"]["used"] = {"answer": "TAKEN", "boundary": "epic"}
            ledger.save()
        seeded = self.ledger(budget)
        code, out = self.open(needs, "--cap", "45", "--expect-cap", "30", "--source", "owner card: +$15")
        self.assertEqual(code, 0, out)
        changed = self.ledger(budget)
        self.assertEqual(spend_ledger.cap_in_force(changed), 45.0)
        self.assertEqual(changed["jobs"], seeded["jobs"])
        self.assertEqual(changed["rounds"], seeded["rounds"])
        self.assertEqual(spend_ledger.totals(changed), (0.0, 25.0))
        self.assertEqual(self.open(needs, "--cap", "45", "--expect-cap", "30", "--source", "owner card: +$15")[0], 0)
        self.assertEqual(self.ledger(budget), changed)
        self.assertEqual(self.open(needs, "--cap", "50", "--expect-cap", "30", "--source", "stale approval")[0], 1)
        self.assertEqual(self.ledger(budget), changed)
        self.assertEqual(self.launch(budget, "over", "21").returncode, 1)
        self.assertEqual(self.launch(budget, "fits", "20").returncode, 0)
        self.assertEqual(self.markers(), ["fits"])

    def test_direct_owner_reapproval_requires_an_existing_owner_cap_and_expected_value(self) -> None:
        needs = {"state": "NO_GO_RECORD", "plan_root": str(self.mock_plan / "direct"), "reason": "legacy plan"}
        self.assertEqual(self.open(needs, "--cap", "45", "--expect-cap", "30", "--source", "owner")[0], 1)
        self.assertEqual(self.open(needs, "--cap", "30", "--source", "owner")[0], 0)
        for extra in [("--cap", "45", "--source", "owner"),
                      ("--cap", "45", "--expect-cap", "20", "--source", "owner"),
                      ("--cap", "45", "--expect-cap", "nan", "--source", "owner"),
                      ("--cap", "45", "--expect-cap", "30"),
                      ("--expect-cap", "30", "--source", "owner")]:
            self.assertNotEqual(self.open(needs, *extra)[0], 0, extra)
        self.assertEqual(self.open(go("a" * 40, 30), "--cap", "45", "--expect-cap", "30", "--source", "owner")[0], 1)

    def test_additional_money_reapproval_cannot_reduce_or_cycle_caps(self) -> None:
        needs = {"state": "NO_GO_RECORD", "plan_root": str(self.mock_plan / "direct"), "reason": "legacy plan"}
        code, out = self.open(needs, "--cap", "30", "--source", "initial")
        self.assertEqual(code, 0, out)
        budget = out.split()[1].rstrip(":")
        self.assertEqual(self.open(needs, "--cap", "45", "--expect-cap", "30", "--source", "approval A")[0], 0)
        approved = self.ledger(budget)
        # A return to 30 would let stale A raise it again, so this extra-money path cannot lower caps.
        self.assertEqual(self.open(needs, "--cap", "30", "--expect-cap", "45", "--source", "later B")[0], 1)
        self.assertEqual(self.open(needs, "--cap", "45", "--expect-cap", "45", "--source", "same amount")[0], 1)
        self.assertEqual(self.ledger(budget), approved)
        self.assertEqual(self.open(needs, "--cap", "45", "--expect-cap", "30", "--source", "approval A")[0], 0)
        self.assertEqual(self.ledger(budget), approved)

    def test_owner_reapproval_cannot_override_a_recorded_or_withdrawn_go(self) -> None:
        plan, budget = self.real_budget(30.0, rounds=1)
        self.assertEqual(self.open_plan(plan)[0], 0)
        for kind in ("go", "withdrawn"):
            if kind == "withdrawn":
                plan.write("epic-7: backlog # put back", commit=None)
                self.launch(budget, "withdrawn", "1")
            before = self.ledger(budget)
            self.assertNotEqual(self.open({"state": "NO_GO_RECORD", "plan_root": str(plan.root),
                "reason": "unavailable"}, "--cap", "45", "--expect-cap", "30", "--source", "owner")[0], 0)
            self.assertEqual(self.ledger(budget), before)

    def round(self, budget: str, boundary: str, use_id: str) -> tuple[int, str]:
        done = subprocess.run([sys.executable, str(LEDGER), "round", "--budget", budget, "--boundary", boundary, "--use-id", use_id],
                              capture_output=True, text=True, env=os.environ.copy())
        return done.returncode, done.stdout

    # The go's rounds are read through the real run_needs from a plan with its own history: `round` reads the go again.
    @staticmethod
    def epic_text(rounds: int, cap: float | None = None) -> str:
        money = "none" if cap is None else f"${cap:g}"
        needs = (f"- **Extra repair rounds:** {rounds} per boundary.\n- **Deferrable criteria:** none.\n"
                 f"- **Money cap:** {money}.\n- **Named actions for an Away card:** none.\n")
        return test_run_needs.epic(needs).replace("### Story 7.1: One\n", "### Story 7.1: One\n\n### Story 7.2: Two\n\n### Story 7.3: Three\n")

    @staticmethod
    def go_message(text: str, date: str = "2026-10-23") -> str:
        approved = "sha256:" + run_needs.approval_text(run_needs.sections(text))
        return (f"plan: go for Epic 7 (go {date})\n\nGo-Epic: 7\nGo-Date: {date}\nApproval-Source: card {date}T09:00Z: 'Go'\n"
                f"Approved-Text: {approved}\nApproved-File: epics/007-fixture.md\n")

    def plan(self, rounds: int, cap: float | None = None) -> "test_run_needs.Plan":
        """Epic 7 (stories 7.1-7.3) with his go recorded; the stand-in `bmn` on PATH resolves the project to it."""
        plan = test_run_needs.Plan()
        self.addCleanup(plan.tmp.cleanup)
        text = self.epic_text(rounds, cap)
        plan.write("epic-7: backlog", text)
        plan.go = plan.write("epic-7: ready # go 2026-10-23", commit=self.go_message(text))
        (self.root / "status.json").write_text(json.dumps(plan.status()))
        return plan

    def real_budget(self, cap: float, rounds: int = 0) -> tuple["test_run_needs.Plan", str]:
        """A real plan whose go gives `cap`, its ledger opened: a paid launch reads that go again (BMN 96 recheck)."""
        plan = self.plan(rounds, cap)
        code, out, budget = self.open_plan(plan)
        self.assertEqual(code, 0, out)
        return plan, budget

    def test_a_paid_launch_reads_the_go_again_and_a_withdrawn_one_starts_nothing(self) -> None:
        plan, budget = self.real_budget(10.0)
        self.assertEqual(self.launch(budget, "a", "2").returncode, 0)
        plan.write("epic-7: backlog # put back", commit=None)  # before any open or round
        refused = self.launch(budget, "b", "2")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("was withdrawn: the go of 2026-10-23 was withdrawn: the row is now backlog", refused.stdout)
        self.assertEqual(self.ledger(budget)["gos"][-1]["kind"], "withdrawn")
        self.assertEqual(self.launch(budget, "c", "2").returncode, 1)  # cap none from then on
        self.assertEqual(self.markers(), ["a"])

    def test_a_plan_conflict_at_open_preserves_the_go_and_consumption(self) -> None:
        plan, budget = self.real_budget(10.0, rounds=3)
        self.assertEqual(self.round(budget, "7.1", "before")[0], 0)
        before = self.ledger(budget)
        (self.root / "status.json").write_text(json.dumps({**plan.status(), "conflicts": [7]}))
        code, out, same = self.open_plan(plan)
        self.assertEqual((code, same), (0, budget), out)
        self.assertIn("PLAN_CONFLICT", out)
        self.assertEqual(self.ledger(budget), before)
        (self.root / "status.json").write_text(json.dumps(plan.status()))
        self.assertEqual(self.open_plan(plan)[0], 0)
        self.assertEqual(self.round(budget, "7.1", "after")[0], 0)
        self.assertEqual(spend_ledger.rounds_used(self.ledger(budget), "7.1"), 2)
        self.assertEqual(self.ledger(budget)["gos"], before["gos"])

    def test_a_plan_conflict_refuses_rounds_and_launches_without_withdrawing(self) -> None:
        plan, budget = self.real_budget(10.0, rounds=3)
        self.assertEqual(self.round(budget, "7.1", "before")[0], 0)
        before = self.ledger(budget)
        (self.root / "status.json").write_text(json.dumps({**plan.status(), "conflicts": [7]}))
        refused = self.launch(budget, "held", "2")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("cannot be confirmed", refused.stdout)
        code, out = self.round(budget, "7.1", "held")
        self.assertEqual(code, 1, out)
        self.assertIn("cannot be confirmed", out)
        self.assertEqual(self.markers(), [])
        self.assertEqual(self.ledger(budget), before)
        (self.root / "status.json").write_text(json.dumps(plan.status()))
        self.assertEqual(self.round(budget, "7.1", "held")[0], 0)
        self.assertEqual(self.ledger(budget)["gos"], before["gos"])

    def test_a_missing_default_checkout_holds_without_withdrawing_the_go(self) -> None:
        plan, budget = self.real_budget(10.0, rounds=3)
        before = self.ledger(budget)
        (self.root / "status.json").write_text(json.dumps({**plan.status(), "default_available": False}))
        refused = self.launch(budget, "held", "2")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("cannot be confirmed", refused.stdout)
        self.assertEqual(self.round(budget, "7.1", "held")[0], 1)
        self.assertIn("NO_DEFAULT_CHECKOUT", self.open_plan(plan)[1])
        self.assertEqual(self.ledger(budget), before)
        (self.root / "status.json").write_text(json.dumps(plan.status()))
        self.assertEqual(self.round(budget, "7.1", "held")[0], 0)
        self.assertEqual(self.ledger(budget)["gos"], before["gos"])

    def test_a_later_hand_go_that_names_no_act_withdraws_the_go_in_force_at_open(self) -> None:
        plan, budget = self.real_budget(10.0, rounds=1)
        plan.write("epic-7: backlog # put back")
        plan.write("epic-7: ready # go 2026-10-24", commit="plan: go by hand")  # after a recorded go: it names no act
        refused = self.launch(budget, "a", "1")  # the first ledger call after it, here a launch, records the withdrawal
        self.assertEqual(refused.returncode, 1)
        self.assertIn("was withdrawn", refused.stdout)
        self.assertEqual(self.ledger(budget)["gos"][-1]["kind"], "withdrawn")
        code, out, again = self.open_plan(plan)
        self.assertEqual((code, again), (0, budget), out)
        self.assertIn("GO: withdrawn", out)
        self.assertIn("cap none", out)
        self.assertEqual(self.round(budget, "7.1", "a:7.1")[0], 1)
        self.assertEqual(self.markers(), [])
        # Opened first instead, the same plan is withdrawn at open.
        other, opened = self.real_budget(10.0, rounds=1)
        other.write("epic-7: backlog # put back")
        other.write("epic-7: ready # go 2026-10-24", commit="plan: go by hand")
        self.assertIn("GO: withdrawn", self.open_plan(other)[1])
        self.assertEqual(self.ledger(opened)["gos"][-1]["kind"], "withdrawn")

    def open_plan(self, plan: "test_run_needs.Plan") -> tuple[int, str, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = spend_ledger.main(["open", "--epic", "7", "--project", str(plan.root.parent)])
        return code, out.getvalue(), out.getvalue().split()[1].rstrip(":")

    def test_the_gos_rounds_are_one_count_for_every_lead_resume_and_retry(self) -> None:
        plan = self.plan(rounds=1)
        code, out, budget = self.open_plan(plan)
        self.assertEqual(code, 0, out)
        self.assertIn(f"GO: 2026-10-23 commit {plan.go[:12]}; source card 2026-10-23T09:00Z: 'Go'", out)
        self.assertIn("ROUNDS: 1 extra per boundary from this go; none used", out)
        self.assertEqual(self.round(budget, "7.2", "7.2:round-1")[0], 0)
        self.assertEqual(self.round(budget, "7.2", "7.2:round-1"), (0, self.round(budget, "7.2", "7.2:round-1")[1]))  # a retry: the first answer
        self.assertIn("nothing taken again", self.round(budget, "7.2", "7.2:round-1")[1])
        # A resumed or replacement lead under another run name finds the same count: the boundary is the story, not the run.
        refused = self.round(budget, "7.2", "replacement-run:7.2:round-1")
        self.assertEqual(refused[0], 1)
        self.assertIn("1 are used at 7.2", refused[1])
        self.assertEqual(self.round(budget, "epic", "epic:round-1")[0], 0)  # another boundary has its own
        _, status, _ = self.open_plan(plan)
        self.assertIn("ROUNDS: 1 extra per boundary from this go; 7.2 1 used, epic 1 used", status)

    def test_a_free_boundary_name_or_another_epics_story_is_refused(self) -> None:
        _, _, budget = self.open_plan(self.plan(rounds=2))
        for boundary in ("7.2-review", "renamed-gate", "8.1", "7.99", ""):  # 7.99: no such story at the go
            self.assertEqual(self.round(budget, boundary, f"{boundary}:1")[0], 2, boundary)
        self.assertEqual(self.ledger(budget)["rounds"], {})
        for wrong in ("bmn", "UNABLE:"):  # what a failed open's first line leaves in a caller's variable
            self.assertEqual(self.round(wrong, "7.1", "7.1:1"), (2, f"UNABLE: not a budget id: {wrong}\n"), wrong)

    def test_a_lost_ledger_counts_the_rounds_of_a_go_a_run_already_began_under_as_used(self) -> None:
        plan = self.plan(rounds=1)
        handoff = plan.root.parent / ".dev-auto" / "handoff.md"
        handoff.parent.mkdir(parents=True)
        handoff.write_text(f"- Go: GO: 2026-10-23 commit {plan.go[:12]}; source card; ROUNDS: 1 extra per boundary from this go; 7.1 1 used\n")
        code, out, budget = self.open_plan(plan)
        self.assertEqual(code, 0, out)
        self.assertIn("ROUNDS: 1 extra per boundary from this go; 7.1 1 used, 7.2 1 used, 7.3 1 used, epic 1 used", out)
        self.assertIn("names this go, the ledger does not: up to 1 extra per boundary counted as used", out)
        self.assertEqual(self.round(budget, "7.2", "resumed:7.2")[0], 1)
        # With the handoff gone too, a row already past ready says a run began under this go.
        started = self.plan(rounds=1)
        started.write("epic-7: in-progress # go 2026-10-23")
        _, out, budget = self.open_plan(started)
        self.assertIn("the epic's row is already in-progress, the ledger does not: up to 1 extra per boundary counted as used", out)
        self.assertEqual(self.round(budget, "7.2", "resumed:7.2")[0], 1)
        # A handoff naming another go takes nothing from this one.
        fresh = self.plan(rounds=1)
        (fresh.root.parent / ".dev-auto").mkdir()
        (fresh.root.parent / ".dev-auto" / "handoff.md").write_text("- Go: GO: 2026-10-20 commit bbbbbbbbbbbb; source card\n")
        _, out, _ = self.open_plan(fresh)
        self.assertIn("ROUNDS: 1 extra per boundary from this go; none used", out)

    def test_rounds_counted_as_used_at_recovery_stay_used_after_his_next_go(self) -> None:
        # Astra review A5: recovery's presumed use is kept in the ledger, so a reapproval refills only what it adds.
        plan = self.plan(rounds=1)
        plan.write("epic-7: in-progress # go 2026-10-23")
        _, out, budget = self.open_plan(plan)
        self.assertEqual(self.round(budget, "7.1", "a:7.1")[0], 1)
        plan.write("epic-7: ready # go 2026-10-24", commit=self.go_message(self.epic_text(1), "2026-10-24"))
        _, out, again = self.open_plan(plan)
        self.assertEqual(again, budget)
        self.assertIn("ROUNDS: 1 extra per boundary from this go; 7.1 1 used", out)
        self.assertEqual(self.round(budget, "7.1", "b:7.1")[0], 1)  # the same allowance: nothing comes back
        plan.write("epic-7: in-progress # go 2026-10-24")
        plan.write("epic-7: ready # go 2026-10-25", self.epic_text(2), commit=self.go_message(self.epic_text(2), "2026-10-25"))
        self.open_plan(plan)
        self.assertEqual(self.round(budget, "7.1", "c:7.1")[0], 0)  # one more allowed: one more round
        self.assertEqual(self.round(budget, "7.1", "d:7.1")[0], 1)
        # A recovery under a go whose earlier go allowed more counts the larger allowance as used.
        larger = self.plan(rounds=3)
        larger.write("epic-7: in-progress # go 2026-10-23")
        larger.write("epic-7: ready # go 2026-10-24", self.epic_text(1), commit=self.go_message(self.epic_text(1), "2026-10-24"))
        larger.write("epic-7: in-progress # go 2026-10-24")
        _, out, other = self.open_plan(larger)
        self.assertIn("7.1 3 used", out)
        larger.write("epic-7: ready # go 2026-10-25", self.epic_text(3), commit=self.go_message(self.epic_text(3), "2026-10-25"))
        self.open_plan(larger)
        self.assertEqual(self.round(other, "7.1", "a:7.1")[0], 1)

    def test_a_withdrawal_in_the_history_stops_a_paid_launch_without_another_open(self) -> None:
        # Astra review A2: put back and moved on with no new go; the next launch reads the go again and starts nothing.
        plan, budget = self.real_budget(10.0)
        self.assertEqual(self.launch(budget, "a", "2").returncode, 0)
        plan.write("epic-7: backlog # withdrawn")
        plan.write("epic-7: in-progress # go 2026-10-23")
        refused = self.launch(budget, "b", "2")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("was withdrawn", refused.stdout)
        self.assertEqual(self.markers(), ["a"])

    def test_a_row_taken_off_the_board_stops_a_paid_launch_without_another_open(self) -> None:
        # Astra recheck R2: the epic's row removed from the board, not committed; the next launch starts nothing.
        plan, budget = self.real_budget(10.0)
        self.assertEqual(self.launch(budget, "a", "2").returncode, 0)
        plan.write("epic-8: backlog", commit=None)
        refused = self.launch(budget, "b", "2")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("was withdrawn", refused.stdout)
        self.assertEqual(self.markers(), ["a"])

    def test_a_fresh_bmad_go_at_backlog_keeps_its_rounds(self) -> None:
        # Astra recheck R3: a BMAD go is a dated comment, often on a backlog row; no run began, so nothing is counted as used.
        out, budget = self.bmad_open("bmad")
        self.assertIn("ROUNDS: 1 extra per boundary from this go; none used", out)
        self.assertEqual(self.round(budget, "7.1", "a:7.1")[0], 0)
        # A handoff naming the go still says a run began under it, whatever the row's status.
        out, budget = self.bmad_open("bmad-resumed", handoff=True)
        self.assertIn("7.1 1 used", out)
        self.assertEqual(self.round(budget, "7.1", "a:7.1")[0], 1)

    def test_an_unknown_row_status_counts_the_rounds_as_used(self) -> None:
        plan = self.plan(rounds=1)
        plan.write("epic-7: weird # go 2026-10-23")
        _, out, budget = self.open_plan(plan)
        self.assertIn("the epic's row is already weird", out)
        self.assertEqual(self.round(budget, "7.1", "a:7.1")[0], 1)

    def bmad_open(self, name: str, handoff: bool = False) -> tuple[str, str]:
        """A BMAD project whose go is a dated comment on a backlog row, its ledger opened."""
        root = self.root / name
        (root / "_bmad-output" / "implementation-artifacts").mkdir(parents=True)
        (root / "_bmad-output" / "planning-artifacts").mkdir(parents=True)
        run = lambda *a: subprocess.run(["git", "-C", str(root), "-c", "user.name=F", "-c", "user.email=f@example.invalid", *a],
                                        check=True, capture_output=True, text=True).stdout.strip()
        run("init", "-qb", "main")
        sprint = root / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml"
        (root / "_bmad-output" / "planning-artifacts" / "epics.md").write_text(
            "# Epics\n\n## Epic 7: Fixture\n\n### Run needs\n\n- **Extra repair rounds:** 1 per boundary.\n- **Money cap:** none.\n\n### Story 7.1: One\n")
        sprint.write_text("development_status:\n  epic-7: backlog\n")
        run("add", "-A"); run("commit", "-qm", "docs: plan")
        sprint.write_text("development_status:\n  epic-7: backlog # go 2026-10-21\n")
        run("commit", "-qam", "docs: go")
        if handoff:
            (root / ".dev-auto").mkdir()
            (root / ".dev-auto" / "handoff.md").write_text(f"- Go: GO: 2026-10-21 commit {run('rev-parse', 'HEAD')[:12]}; source not recorded\n")
        (self.root / "status.json").write_text(json.dumps({"ok": True, "format": "bmad", "history": "product-repository", "plan_root": None,
                                                           "board": str(sprint), "board_checkout": str(root), "product_root": str(root)}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(spend_ledger.main(["open", "--epic", "7", "--project", str(root)]), 0)
        return out.getvalue(), out.getvalue().split()[1].rstrip(":")

    def test_a_second_go_on_the_same_day_with_a_lower_cap_is_the_cap_in_force(self) -> None:
        # Astra review A3: his newer go on the same date lowers the cap; nothing launches above it.
        plan, budget = self.real_budget(10.0)
        lower = self.epic_text(0, 3.0)
        plan.write(text=lower, commit="docs: lower the cap")
        plan.write(commit=self.go_message(lower).replace("T09:00Z: 'Go'", "T11:00Z: 'Go, $3 only'"))
        self.assertEqual(self.launch(budget, "a", "5").returncode, 1)  # the go in force is no longer the one opened
        code, out, again = self.open_plan(plan)
        self.assertEqual((code, again), (0, budget), out)
        self.assertIn("cap 3.00", out)
        self.assertEqual(self.launch(budget, "b", "5").returncode, 1)
        self.assertEqual(self.launch(budget, "c", "2").returncode, 0)
        self.assertEqual(self.markers(), ["c"])

    def test_a_withdrawn_go_gives_no_round_and_no_paid_launch(self) -> None:
        plan = self.plan(rounds=2)
        _, _, budget = self.open_plan(plan)
        self.assertEqual(self.round(budget, "7.1", "a:7.1")[0], 0)
        plan.write("epic-7: backlog # put back", commit=None)  # the row he put back, not yet committed
        refused = self.round(budget, "7.1", "b:7.1")
        self.assertEqual(refused[0], 1)
        self.assertIn("was withdrawn: the go of 2026-10-23 was withdrawn: the row is now backlog", refused[1])
        self.assertEqual(self.ledger(budget)["gos"][-1]["kind"], "withdrawn")
        _, out, _ = self.open_plan(plan)
        self.assertIn("GO: withdrawn (the go of 2026-10-23 was withdrawn: the row is now backlog)", out)
        self.assertIn("cap none", out)
        self.assertEqual(self.round(budget, "7.2", "c:7.2")[0], 1)

    def test_two_leads_taking_the_last_round_at_once_get_exactly_one(self) -> None:
        _, _, budget = self.open_plan(self.plan(rounds=1))
        argv = lambda use: [sys.executable, str(LEDGER), "round", "--budget", budget, "--boundary", "7.1", "--use-id", use]
        runs = [subprocess.Popen(argv(f"lead-{n}:7.1"), stdout=subprocess.PIPE, text=True, env=os.environ.copy()) for n in range(4)]
        codes = sorted(run.wait() for run in runs)
        self.assertEqual(codes, [0, 1, 1, 1])

    def test_a_reapproval_refills_no_round_used_and_no_go_gives_none(self) -> None:
        plan = self.plan(rounds=1)
        _, _, budget = self.open_plan(plan)
        self.assertEqual(self.round(budget, "7.1", "a:7.1")[0], 0)
        plan.write("epic-7: in-progress # go 2026-10-23")
        plan.write("epic-7: ready # go 2026-10-24", commit=self.go_message(self.epic_text(1), "2026-10-24"))
        self.open_plan(plan)
        self.assertEqual(self.round(budget, "7.1", "b:7.1")[0], 1)
        plan.write("epic-7: in-progress # go 2026-10-24")
        plan.write("epic-7: ready # go 2026-10-25", self.epic_text(2), commit=self.go_message(self.epic_text(2), "2026-10-25"))
        _, out, _ = self.open_plan(plan)
        self.assertIn("ROUNDS: 2 extra per boundary from this go; 7.1 1 used", out)
        self.assertEqual(self.round(budget, "7.1", "c:7.1")[0], 0)  # his new go gave one more
        none = {"state": "NO_GO_RECORD", "plan_root": str(self.mock_plan / "other"), "reason": "no go"}
        code, out = self.open(none, "--cap", "5", "--source", "owner 2026-10-23: up to $5")
        other = out.split()[1].rstrip(":")
        self.assertIn("GO: none recorded; no extra repair rounds", out)
        refused = self.round(other, "7.1", "x:7.1")
        self.assertEqual(refused[0], 1)
        self.assertIn("no recorded go gives extra rounds", refused[1])

if __name__ == "__main__":
    unittest.main()
