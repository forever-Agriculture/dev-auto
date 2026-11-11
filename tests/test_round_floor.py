# MODULE: test_round_floor.py - BMN Story 106.7: 4 extra rounds by default, never reopening what he stopped, and a real step-back before the last
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "dev-auto" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_needs  # noqa: E402
sys.path.insert(0, str(REPO / "tests"))
import test_run_needs  # noqa: E402

LEDGER = SCRIPTS / "spend_ledger.py"
STUB = """#!/bin/sh
if [ "$1 $2 $3" = "team asks show" ]; then cat "{root}/asks/$4.json" 2>/dev/null || exit 1; exit 0; fi
cat "{root}/status.json"
"""


def text(rounds: str | None) -> str:
    needs = None if rounds is None else f"- **Extra repair rounds:** {rounds} per boundary.\n- **Money cap:** none.\n- **Named actions for an Away card:** none.\n"
    return test_run_needs.epic(needs).replace("### Story 7.1: One\n", "### Story 7.1: One\n\n### Story 7.2: Two\n")


def go_message(body: str) -> str:
    approved = "sha256:" + run_needs.approval_text(run_needs.sections(body))
    return ("plan: go for Epic 7 (go 2026-10-23)\n\nGo-Epic: 7\nGo-Date: 2026-10-23\nApproval-Source: card 2026-10-23T09:00Z: 'Go'\n"
            f"Approved-Text: {approved}\nApproved-File: epics/007-fixture.md\n")


class Floor(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "bin").mkdir()
        (self.root / "asks").mkdir()
        stub = self.root / "bin" / "bmn"
        stub.write_text(STUB.format(root=self.root))
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        patcher = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "state"), "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.plan = test_run_needs.Plan()
        self.addCleanup(self.plan.tmp.cleanup)
        self.record = self.root / "failed-methods.md"
        self.record.write_text("method A failed: X\nmethod B failed: Y\n")

    def status(self) -> None:
        (self.root / "status.json").write_text(json.dumps(self.plan.status()))

    def ledger(self, *argv: str) -> tuple[int, str]:
        done = subprocess.run([sys.executable, str(LEDGER), *argv], capture_output=True, text=True, env=os.environ.copy(), cwd=self.root)
        return done.returncode, done.stdout + done.stderr

    def open(self) -> tuple[str, str]:
        code, out = self.ledger("open", "--epic", "7", "--project", str(self.plan.root))
        self.assertEqual(code, 0, out)
        self.budget = out.split()[1].rstrip(":")
        return self.budget, out

    def round(self, budget: str, boundary: str, use: str, *extra: str) -> tuple[int, str]:
        return self.ledger("round", "--budget", budget, "--boundary", boundary, "--use-id", use, *extra)

    def go_with(self, rounds: str | None, row: str = "epic-7: ready # go 2026-10-23") -> None:
        body = text(rounds)
        self.plan.write("epic-7: backlog", body)
        self.plan.write(row, commit=go_message(body))
        self.status()

    def no_go(self, rounds: str | None = "2") -> None:
        self.plan.write("epic-7: backlog", text(rounds))
        self.status()

    def ask(self, ask_id: str = "a1", *, boundary: str = "7.1", budget: str | None = None, role: str = "consultant", agent: str = "astra",
            state: str = "answered", answer: str = "Try a different seam.", record: str | None = None) -> str:
        folder = self.root / "runs" / ask_id
        folder.mkdir(parents=True)
        digest = hashlib.sha256((self.record.read_text() if record is None else record).encode()).hexdigest()
        (folder / "question.md").write_text(f"Brief.\nStep-back: budget {budget or self.budget} boundary {boundary} record sha256:{digest}\n")
        (self.root / "asks" / f"{ask_id}.json").write_text(json.dumps({"id": ask_id, "state": state, "exit": "0" if state == "answered" else "1",
            "role": role, "teammate": {"agent": agent}, "answer": answer, "record": str(folder)}))
        return ask_id

    def step_back(self, ask_id: str, method: str = "a different seam") -> tuple[str, ...]:
        return ("--step-back", ask_id, "--record", str(self.record), "--method", method, "--lead", "opus")

    def take_three(self, budget: str, boundary: str = "7.1") -> None:
        for n in range(1, 4):
            code, out = self.round(budget, boundary, f"{boundary}:r{n}")
            self.assertEqual(code, 0, out)

    # AC1
    def test_no_go_ever_recorded_gives_four(self) -> None:
        self.no_go()
        budget, out = self.open()
        self.assertIn("4 extra repair rounds per boundary", out)
        self.take_three(budget)
        code, out = self.round(budget, "7.1", "7.1:r4", *self.step_back(self.ask()))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.round(budget, "7.1", "7.1:r5")[0], 1)

    def test_no_run_needs_gives_four(self) -> None:
        self.no_go(None)
        budget, out = self.open()
        self.assertIn("4 extra repair rounds per boundary", out)
        self.assertEqual(self.round(budget, "7.2", "x")[0], 0)

    def test_a_go_with_fewer_gets_four_and_more_keeps_its_number(self) -> None:
        self.go_with("2")
        _, out = self.open()
        self.assertIn("ROUNDS: 4 extra per boundary", out)
        other = test_run_needs.Plan()
        self.addCleanup(other.tmp.cleanup)
        self.plan = other
        self.go_with("6")
        _, out = self.open()
        self.assertIn("ROUNDS: 6 extra per boundary", out)

    def test_a_free_story_name_is_no_boundary_without_a_go(self) -> None:
        self.no_go()
        budget, _ = self.open()
        self.assertNotEqual(self.round(budget, "7.99", "x")[0], 0)

    # AC2
    def test_a_withdrawn_go_gets_no_floor(self) -> None:
        self.go_with("4")
        budget, _ = self.open()
        self.plan.write("epic-7: backlog # put back")
        self.status()
        _, out = self.open()
        self.assertIn("GO: withdrawn", out)
        self.assertEqual(self.round(budget, "7.1", "x")[0], 1)

    def test_an_unconfirmable_go_gets_no_floor(self) -> None:
        body = text("4")
        self.plan.write("epic-7: backlog", body)
        self.plan.write("epic-7: ready # go 2026-10-23", commit="plan: go for Epic 7 (go 2026-10-23)\n\nGo-Epic: 7\nGo-Date: 2026-10-23\n")
        self.status()
        budget, out = self.open()
        self.assertNotIn("4 extra repair rounds per boundary", out)
        self.assertEqual(self.round(budget, "7.1", "x")[0], 1)

    def test_his_narrower_instruction_holds_and_cannot_be_raised(self) -> None:
        self.go_with("4")
        budget, _ = self.open()
        code, out = self.ledger("limit", "--budget", budget, "--rounds", "1", "--source", "'one more only' 2026-11-04T19:00")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ledger("limit", "--budget", budget, "--rounds", "3", "--source", "lead")[0], 1)
        self.assertEqual(self.ledger("limit", "--budget", budget, "--rounds", "1")[0], 2)
        code, out = self.round(budget, "7.1", "a", *self.step_back(self.ask()))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.round(budget, "7.1", "b")[0], 1)
        self.assertIn("limit 1", self.open()[1])

    def test_spent_rounds_stay_spent_when_the_floor_rises_above_them(self) -> None:
        self.go_with("2")
        budget, _ = self.open()
        for use in ("a", "b"):
            self.assertEqual(self.round(budget, "7.1", use)[0], 0)
        self.assertIn("7.1 2 used", self.open()[1])
        self.assertEqual(self.round(budget, "7.1", "c")[0], 0)
        self.assertEqual(self.round(budget, "7.1", "d")[0], 1)  # the last needs its step-back

    # AC3
    def test_the_last_round_refuses_without_a_step_back_and_can_be_retried(self) -> None:
        self.go_with("4")
        budget, _ = self.open()
        self.take_three(budget)
        code, out = self.round(budget, "7.1", "last")
        self.assertEqual(code, 1)
        self.assertIn("step-back", out)
        self.assertEqual(self.round(budget, "7.1", "last", *self.step_back(self.ask()))[0], 0)

    def refused(self, argv) -> None:
        self.go_with("4")
        budget, _ = self.open()
        self.take_three(budget)
        code, out = self.round(budget, "7.1", "last", *argv())
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED", out)

    def test_senior_consultant_can_answer_the_step_back(self) -> None:
        self.go_with("4")
        budget, _ = self.open()
        self.take_three(budget)
        code, out = self.round(budget, "7.1", "last", *self.step_back(self.ask(role="senior-consultant")))
        self.assertEqual(code, 0, out)

    def test_another_boundarys_ask_refuses(self) -> None:
        self.refused(lambda: self.step_back(self.ask(boundary="7.2")))

    def test_another_epics_ask_refuses(self) -> None:
        self.go_with("4")
        budget, _ = self.open()
        self.take_three(budget)
        code, out = self.round(budget, "7.1", "last", *self.step_back(self.ask(budget=budget.rsplit("-", 1)[0] + "-epic-8")))
        self.assertEqual(code, 1, out)

    # Astra's full review, finding 4: the ask names the plan, not only an epic number.
    def test_another_projects_ask_with_the_same_numbers_refuses(self) -> None:
        self.go_with("4")
        budget, _ = self.open()
        self.take_three(budget)
        elsewhere = "0123456789abcdef-epic-7"
        self.assertNotEqual(budget, elsewhere)
        code, out = self.round(budget, "7.1", "last", *self.step_back(self.ask(budget=elsewhere)))
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED", out)
        self.assertIn(f"Step-back: budget {budget} boundary 7.1", out)

    def test_another_checkout_of_the_same_plan_keeps_the_ask(self) -> None:
        self.go_with("4")
        budget, _ = self.open()
        self.take_three(budget)
        linked = self.root / "linked"
        subprocess.run(["git", "-C", str(self.plan.root), "worktree", "add", "-q", "--detach", str(linked)], check=True)
        self.addCleanup(subprocess.run, ["git", "-C", str(self.plan.root), "worktree", "remove", "--force", str(linked)], capture_output=True)
        status = json.loads((self.root / "status.json").read_text())
        status.update({key: value.replace(str(self.plan.root), str(linked)) for key, value in status.items() if isinstance(value, str)})
        (self.root / "status.json").write_text(json.dumps(status))
        code, out = self.ledger("open", "--epic", "7", "--project", str(linked))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.split()[1].rstrip(":"), budget)
        code, out = self.round(budget, "7.1", "last", *self.step_back(self.ask()))
        self.assertEqual(code, 0, out)

    def test_a_failed_ask_refuses(self) -> None:
        self.refused(lambda: self.step_back(self.ask(state="failed")))

    def test_an_empty_answer_refuses(self) -> None:
        self.refused(lambda: self.step_back(self.ask(answer=" ")))

    def test_a_reviewers_ask_refuses(self) -> None:
        self.refused(lambda: self.step_back(self.ask(role="epic-reviewer")))

    def test_the_lead_answering_itself_refuses(self) -> None:
        self.refused(lambda: self.step_back(self.ask(agent="opus")))

    def test_a_stale_failed_method_record_refuses(self) -> None:
        self.refused(lambda: self.step_back(self.ask(record="an older record\n")))

    def test_an_unknown_ask_refuses(self) -> None:
        self.refused(lambda: self.step_back("missing"))

    def test_no_method_refuses(self) -> None:
        self.refused(lambda: ("--step-back", self.ask(), "--record", str(self.record), "--lead", "opus"))

    # Astra's full review, finding 3: the production floor, a lost ledger, and what recovery counts as spent.
    def test_a_lost_ledger_does_not_refill_a_floor_a_small_go_gave(self) -> None:
        for raw in ("0", "2"):
            with self.subTest(raw=raw):
                self.plan = test_run_needs.Plan()
                self.addCleanup(self.plan.tmp.cleanup)
                self.go_with(raw)
                self.plan.write("epic-7: in-progress # go 2026-10-23")
                self.status()
                budget, out = self.open()
                self.assertIn("up to 4 extra per boundary counted as used", out)
                self.assertIn("7.1 4 used", out)
                code, out = self.round(budget, "7.1", "after-loss", *self.step_back(self.ask(f"a{raw}")))
                self.assertEqual(code, 1, out)
                self.assertIn("4 are used", out)

    def test_a_later_go_gives_only_what_it_adds_over_a_lost_floor(self) -> None:
        self.go_with("0")
        self.plan.write("epic-7: in-progress # go 2026-10-23")
        self.status()
        budget, _ = self.open()
        body = text("6")
        self.plan.write("epic-7: backlog # put back", body)
        self.plan.write("epic-7: ready # go 2026-10-24", commit=go_message(body).replace("2026-10-23", "2026-10-24"))
        self.status()
        self.assertEqual(self.open()[0], budget)
        self.assertEqual(self.round(budget, "7.1", "more-1")[0], 0)
        self.assertEqual(self.round(budget, "7.1", "more-2", *self.step_back(self.ask()))[0], 0)
        self.assertEqual(self.round(budget, "7.1", "more-3")[0], 1)

    def test_a_lost_ledger_does_not_refill_the_floor_with_no_go(self) -> None:
        self.plan.write("epic-7: in-progress", text("2"))
        self.status()
        budget, out = self.open()
        self.assertIn("7.1 4 used", out)
        self.assertEqual(self.round(budget, "7.1", "after-loss", *self.step_back(self.ask()))[0], 1)

    def test_a_row_not_started_with_no_go_keeps_its_four(self) -> None:
        self.no_go()
        budget, out = self.open()
        self.assertNotIn("used", next(line for line in out.splitlines() if line.startswith("GO:")))
        self.assertEqual(self.round(budget, "7.1", "first")[0], 0)

    def test_a_reused_ask_refuses_and_the_method_must_differ(self) -> None:
        self.go_with("4")
        budget, _ = self.open()
        self.take_three(budget)
        first = self.ask()
        self.assertEqual(self.round(budget, "7.1", "last", *self.step_back(first))[0], 0)
        self.take_three(budget, "7.2")
        self.ask("a2", boundary="7.2")
        self.assertEqual(self.round(budget, "7.2", "l", *self.step_back(first))[0], 1)

    def test_the_ledger_keeps_the_ask_and_the_method_and_a_retry_answers_first(self) -> None:
        self.go_with("4")
        budget, _ = self.open()
        self.take_three(budget)
        argv = self.step_back(self.ask(), "drop the cache")
        self.assertEqual(self.round(budget, "7.1", "last", *argv)[0], 0)
        self.assertEqual(self.round(budget, "7.1", "last", *argv)[0], 0)
        data = json.loads((self.root / "state" / "dev-auto" / "budgets" / f"{budget}.json").read_text())
        self.assertEqual(data["rounds"]["last"]["step_back"], "a1")
        self.assertEqual(data["rounds"]["last"]["method"], "drop the cache")


class Words(unittest.TestCase):
    """AC4-AC5: the skill parks; it never retries on his answer or asks for a round."""

    def read(self, name: str) -> str:
        return (REPO / "skills" / "dev-auto" / name).read_text(encoding="utf-8")

    def test_the_skill_parks_and_never_waits_for_his_answer(self) -> None:
        skill = self.read("SKILL.md")
        self.assertNotIn("retrying only on\nhis answer", skill)
        self.assertNotIn("retrying only on his answer", skill)
        self.assertNotIn("without the extras", skill)
        self.assertNotIn("the brake's\ndecision", skill)
        self.assertIn("references/step-back-brief.md", skill)

    def test_the_skill_carries_his_consent_with_its_limits(self) -> None:
        # BMN 106.21: he placed it here, not in his global rules; finishing a ticket stays out.
        skill = (REPO / "skills" / "dev-auto" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("move its own ticket to In progress, Blocked or In review, and publish its private reports", skill)
        self.assertIn("a recorded go authorizes the messages its Run needs name", skill)
        self.assertNotIn("its own ticket to Done", skill)

    def test_the_brief_asks_the_four_questions(self) -> None:
        brief = self.read("references/step-back-brief.md")
        for words in ("goal or the criterion wrong", "real cause", "drop", "different method", "Step-back: budget"):
            self.assertIn(words, brief)

    def test_the_away_card_asks_no_rounds(self) -> None:
        away = self.read("references/away-grant.md")
        self.assertNotIn("extra repair rounds per boundary (2, 3 or 4)", away)


if __name__ == "__main__":
    unittest.main()
