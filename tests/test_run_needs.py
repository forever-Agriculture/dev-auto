# MODULE: test_run_needs.py - BMN Epic 90.3: the owner's go and its Run needs, read from a plan's history
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "dev-auto" / "scripts"))
import run_needs  # noqa: E402

NEEDS = ("- **Extra repair rounds:** 2 per boundary.\n"
         "- **Deferrable criteria:** 7.2 AC3 when the screen cannot be read.\n"
         "- **Money cap:** $15 for review asks.\n"
         "- **Named actions for an Away card:** none.\n")


def epic(needs: str | None = NEEDS, decisions: str = "- D1: yes.\n") -> str:
    text = "# Epic 7: Fixture\n\n## Outcome\n\nIt works.\n\n"
    if needs is not None:
        text += f"## Run needs\n\n{needs}\n"
    return text + f"## Decisions\n\n{decisions}\n## Stories\n\n### Story 7.1: One\n"


def board(line: str) -> str:
    return f"format: bmn-plan\nschema_version: 1\nqueue:\ndevelopment_status:\n  epic-6: done\n\n  {line}\n  7-1-one: backlog\n"


class Plan:
    """An ignored plan with its own history, as BMN's is."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "plan"
        (self.root / "epics").mkdir(parents=True)
        self.git("init", "-qb", "main")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=F", "-c", "user.email=f@example.invalid", *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def write(self, row: str | None = None, text: str | None = None, commit: str | None = "plan") -> str:
        if row is not None:
            (self.root / "status.yaml").write_text(board(row))
        if text is not None:
            (self.root / "epics" / "007-fixture.md").write_text(text)
        if commit is None:
            return ""
        self.git("add", "-A")
        self.git("commit", "-qm", commit, "--allow-empty")
        return self.git("rev-parse", "HEAD")

    def status(self) -> dict:
        return {"ok": True, "format": "bmn-plan", "history": "plan-repository", "plan_root": str(self.root),
                "board": str(self.root / "status.yaml"), "board_checkout": str(self.root.parent), "product_root": str(self.root.parent)}

    def read(self) -> dict:
        with mock.patch.object(run_needs, "resolve", return_value=self.status()):
            return run_needs.run_needs(self.root.parent, 7)


class RunNeedsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = Plan()
        self.addCleanup(self.plan.tmp.cleanup)

    def test_go_found_after_the_row_moved_on(self) -> None:
        self.plan.write("epic-7: backlog # planned", epic())
        go = self.plan.write("epic-7: ready # go 2026-10-20")
        self.plan.write("epic-7: in-progress # go 2026-10-20; run on dev-auto/epic-7")
        self.plan.write("epic-7: review # implemented")
        result = self.plan.read()
        self.assertEqual((result["state"], result["go_date"], result["go_commit"]), ("GO", "2026-10-20", go))
        self.assertEqual(result["parsed"], {"rounds": 2, "deferrable": ["7.2 AC3 when the screen cannot be read."],
                                            "money_cap": 15.0, "named_actions": None})
        self.assertEqual(result["changed_since_go"], [])

    def test_an_unrelated_commit_while_ready_keeps_the_same_go(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        go = self.plan.write("epic-7: ready # go 2026-10-20")
        (self.plan.root / "PLAN.md").write_text("frame\n")
        self.plan.write(commit="unrelated")
        self.plan.write("epic-7: ready # go 2026-10-20", commit="board touched, row unchanged")
        self.assertEqual(self.plan.read()["go_commit"], go)

    def test_a_run_needs_edit_while_ready_is_changed_since_go_and_the_gos_text_holds(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        self.plan.write("epic-7: ready # go 2026-10-20")
        self.plan.write(text=epic(NEEDS.replace("2 per boundary", "4 per boundary")), commit="edit while ready")
        result = self.plan.read()
        self.assertEqual(result["changed_since_go"], ["Run needs"])
        self.assertEqual(result["parsed"]["rounds"], 2)
        self.plan.write(text=epic(decisions="- D1: no.\n"), commit=None)  # uncommitted edits count too
        self.assertEqual(self.plan.read()["changed_since_go"], ["Decisions"])

    def test_a_reapproval_is_a_new_go_and_names_the_earlier_one(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        first = self.plan.write("epic-7: ready # go 2026-10-20")
        self.plan.write("epic-7: blocked # gate red")
        again = self.plan.write("epic-7: ready # go 2026-10-20")  # back to ready: a reapproval
        result = self.plan.read()
        self.assertEqual(result["go_commit"], again)
        self.assertEqual(result["earlier_gos"], [f"2026-10-20@{first[:12]}"])
        newer = self.plan.write("epic-7: ready # go 2026-10-22", epic(NEEDS.replace("$15", "$25")))
        result = self.plan.read()
        self.assertEqual((result["go_commit"], result["go_date"], result["parsed"]["money_cap"]), (newer, "2026-10-22", 25.0))
        self.assertEqual(len(result["earlier_gos"]), 2)

    def test_a_go_date_first_committed_past_ready_counts_once(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        go = self.plan.write("epic-7: in-progress # go 2026-10-23 (owner /dev-auto 7)")
        self.plan.write("epic-7: review # notes changed, date gone")
        self.plan.write("epic-7: in-progress # go 2026-10-23 again in a note")
        result = self.plan.read()
        self.assertEqual((result["go_commit"], result["earlier_gos"]), (go, []))

    def test_missing_section_is_no_run_needs(self) -> None:
        self.plan.write("epic-7: backlog", epic(needs=None))
        self.plan.write("epic-7: ready # go 2026-10-20")
        self.assertEqual(self.plan.read()["state"], "NO_RUN_NEEDS")
        self.plan.write(text=epic(), commit="Run needs added after the go")
        result = self.plan.read()
        self.assertEqual((result["state"], result["changed_since_go"]), ("NO_RUN_NEEDS", ["Run needs"]))

    def test_no_go_is_no_go_record(self) -> None:
        self.plan.write("epic-7: backlog # planned, no go yet", epic())
        self.plan.write(text=epic(), commit=None)
        self.assertEqual(self.plan.read()["state"], "NO_GO_RECORD")
        self.plan.write("epic-7: ready # go 2026-10-20", commit=None)  # recorded on the board, not committed
        self.assertEqual(self.plan.read()["state"], "NO_GO_RECORD")

    def test_unreadable_history_is_no_go_record(self) -> None:
        self.plan.write("epic-7: ready # go 2026-10-20", epic())
        self.plan.git("update-ref", "-d", "HEAD")
        result = self.plan.read()
        self.assertEqual(result["state"], "NO_GO_RECORD")
        self.assertIn("cannot be read", result["reason"])

    def test_bmad_go_is_the_dated_go_comment_in_the_product_history(self) -> None:
        root = self.plan.root.parent / "product"
        (root / "_bmad-output" / "implementation-artifacts").mkdir(parents=True)
        (root / "_bmad-output" / "planning-artifacts").mkdir(parents=True)
        run = lambda *a: subprocess.run(["git", "-C", str(root), "-c", "user.name=F", "-c", "user.email=f@example.invalid", *a],
                                        check=True, capture_output=True, text=True).stdout.strip()
        run("init", "-qb", "main")
        sprint = root / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml"
        epics = root / "_bmad-output" / "planning-artifacts" / "epics.md"
        epics.write_text("# Epics\n\n## Epic 7: Fixture\n\n### Run needs\n\n" + NEEDS + "\n### Story 7.1: One\n\n## Epic 8: Next\n")
        sprint.write_text("development_status:\n  epic-7: backlog\n")
        run("add", "-A"); run("commit", "-qm", "plan")
        sprint.write_text("development_status:\n  epic-7: backlog # go 2026-10-21\n")
        run("commit", "-qam", "go"); go = run("rev-parse", "HEAD")
        sprint.write_text("development_status:\n  epic-7: in-progress # go 2026-10-21\n")
        run("commit", "-qam", "started")
        status = {"ok": True, "format": "bmad", "history": "product-repository", "plan_root": None,
                  "board": str(sprint), "board_checkout": str(root), "product_root": str(root)}
        with mock.patch.object(run_needs, "resolve", return_value=status):
            result = run_needs.run_needs(root, 7)
        self.assertEqual((result["state"], result["go_commit"], result["parsed"]["rounds"]), ("GO", go, 2))

    def test_cli_prints_the_state_and_never_tracebacks(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        self.plan.write("epic-7: ready # go 2026-10-20")
        script = REPO / "skills" / "dev-auto" / "scripts" / "run_needs.py"
        done = subprocess.run([sys.executable, str(script), "7", "--project", str(self.plan.root.parent)],
                              capture_output=True, text=True, env={"PATH": "/nonexistent"})
        self.assertEqual(done.returncode, 2)
        self.assertTrue(done.stdout.startswith("UNABLE: no bmn command"))
        with mock.patch.object(run_needs, "resolve", return_value=self.plan.status()), \
                mock.patch("sys.stdout.write") as write:
            self.assertEqual(run_needs.main(["7"]), 0)
        printed = "".join(call.args[0] for call in write.call_args_list)
        self.assertIn("GO: epic 7, go 2026-10-20", printed)
        self.assertIn("**Extra repair rounds:** 2 per boundary.", printed)


if __name__ == "__main__":
    unittest.main()
