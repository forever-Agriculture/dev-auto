# MODULE: test_spend_ledger.py - BMN Epic 90.4: one reservation ledger keeps the go's money cap at every paid launch
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

LEDGER = SCRIPTS / "spend_ledger.py"


def go(commit: str, cap: float | None, date: str = "2026-10-23") -> dict:
    return {"state": "GO", "plan_root": "/plans/fixture", "go_date": date, "go_commit": commit,
            "parsed": {"rounds": 0, "deferrable": [], "money_cap": cap, "named_actions": None}}


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        patcher = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "state")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.job = self.root / "job.sh"
        self.marker = self.root / "markers"
        self.job.write_text(f'echo "$1" >> {self.marker}\n')

    def open(self, needs: dict, *extra: str) -> tuple[int, str]:
        out = io.StringIO()
        with mock.patch.object(run_needs, "run_needs", return_value=needs), contextlib.redirect_stdout(out):
            code = spend_ledger.main(["open", "--epic", "7", *extra])
        return code, out.getvalue()

    def open_epic(self, epic: str, needs: dict) -> str:
        out = io.StringIO()
        with mock.patch.object(run_needs, "run_needs", return_value=needs), contextlib.redirect_stdout(out):
            self.assertEqual(spend_ledger.main(["open", "--epic", epic]), 0)
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
        budget = self.budget(go("a" * 40, 10.0))
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
        budget = self.budget(go("a" * 40, 10.0))
        for round_ in range(5):
            self.marker.unlink(missing_ok=True)
            spend_ledger_path = self.root / "state" / "dev-auto" / "budgets" / f"{budget}.json"
            spend_ledger_path.write_text(json.dumps({"gos": [{"kind": "go", "commit": "a" * 40, "cap": 10.0}], "jobs": {}}))
            runs = [self.launch(budget, f"race-{round_}-{n}", "6", wait=False) for n in range(2)]
            outputs = [run.communicate()[0] for run in runs]
            self.assertEqual(sorted(run.returncode for run in runs), [0, 1], outputs)
            self.assertEqual(len(self.markers()), 1)

    def test_settle_release_and_unknown_never_reset_the_total(self) -> None:
        budget = self.budget(go("a" * 40, 10.0))
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
        self.enterContext(mock.patch.object(spend_ledger, "go_follows", return_value=True))
        budget = self.budget(go("a" * 40, 10.0))
        self.assertEqual(self.launch(budget, "a", "6").returncode, 0)
        spend_ledger.main(["settle", "--budget", budget, "--job", "a", "--spent", "6"])
        self.assertEqual(self.budget(go("b" * 40, 12.0, "2026-10-25")), budget)
        self.assertEqual(self.launch(budget, "b", "7").returncode, 1)  # 6 + 7 > 12
        self.assertEqual(self.launch(budget, "c", "6").returncode, 0)  # 6 + 6 = 12
        self.assertEqual([g["cap"] for g in self.ledger(budget)["gos"]], [10.0, 12.0])
        code, out = self.open(go("b" * 40, 12.0), "--cap", "100", "--source", "I said so")
        self.assertEqual((code, out.split(":")[0]), (1, "REFUSED"))

    def test_a_systemd_launch_records_the_bare_unit_name(self) -> None:
        budget = self.budget(go("a" * 40, 10.0))
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
        budget = self.budget(go("a" * 40, 10.0))
        lost = subprocess.TimeoutExpired(["systemd-run"], 60)
        with mock.patch.object(spend_ledger.subprocess, "run", side_effect=lost), contextlib.redirect_stdout(io.StringIO()) as out:
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
        none = {"state": "NO_GO_RECORD", "plan_root": "/plans/other", "reason": "no go"}
        code, out = self.open(none, "--cap", "5", "--source", "owner 2026-10-23: up to $5")
        self.assertEqual(code, 0, out)
        budget = out.split()[1].rstrip(":")
        self.assertEqual(self.launch(budget, "a", "5").returncode, 0)
        self.assertEqual(self.open(none, "--cap", "50", "--source", "more")[0], 1)
        self.assertEqual(self.open(none, "--cap", "5")[0], 2)  # no source


if __name__ == "__main__":
    unittest.main()
