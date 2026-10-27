# MODULE: test_run_needs.py - BMN Epic 90.3: the owner's go and its Run needs, read from a plan's history; 96.1: its recorded act and approved text
from __future__ import annotations

import os
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
        self.date = "2026-10-20T10:00:00Z"  # commits keep this date, so a hand go stays one from before bmn plan go
        self.git("init", "-qb", "main")

    def git(self, *args: str, input: str | None = None) -> str:
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=F", "-c", "user.email=f@example.invalid", *args],
                              check=True, capture_output=True, text=True, input=input,
                              env={**os.environ, "GIT_COMMITTER_DATE": self.date, "GIT_AUTHOR_DATE": self.date}).stdout.strip()

    def write(self, row: str | None = None, text: str | None = None, commit: str | None = "plan") -> str:
        if row is not None:
            (self.root / "status.yaml").write_text(board(row))
        if text is not None:
            (self.root / "epics" / "007-fixture.md").write_text(text)
        if commit is None:
            return ""
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-F", "-", input=commit)
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
        self.assertEqual(result["stories"], ["7.1"])  # the round boundaries the go planned

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

    def test_a_go_date_first_committed_past_ready_delegates_nothing(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        self.plan.write("epic-7: in-progress # go 2026-10-23 (owner /dev-auto 7)")
        self.plan.write("epic-7: review # go 2026-10-24 in a later note")
        self.assertEqual(self.plan.read()["state"], "NO_GO_RECORD")

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
        result = self.plan.read()
        self.assertEqual((result["state"], result["uncommitted_go"]), ("NO_GO_RECORD", "2026-10-20"))  # explains, grants nothing
        self.assertNotIn("parsed", result)
        with mock.patch.object(run_needs, "resolve", return_value=self.plan.status()), mock.patch("sys.stdout.write") as write:
            self.assertEqual(run_needs.main(["7"]), 0)
        printed = "".join(call.args[0] for call in write.call_args_list)
        self.assertIn("never by the run, and he is never asked to restate an approval", printed)
        self.assertIn("UNCOMMITTED_GO: the board names go 2026-10-20", printed)

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
        # Committed after HAND_GO_CUTOVER: a BMAD board keeps its dated go comment, which bmn plan go never records.
        late = {**os.environ, "GIT_COMMITTER_DATE": "2026-10-28T10:00:00Z", "GIT_AUTHOR_DATE": "2026-10-28T10:00:00Z"}
        run = lambda *a: subprocess.run(["git", "-C", str(root), "-c", "user.name=F", "-c", "user.email=f@example.invalid", *a],
                                        check=True, capture_output=True, text=True, env=late).stdout.strip()
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

    def test_a_go_committed_by_hand_once_bmn_plan_go_records_gos_grants_nothing(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        self.plan.date = "2026-10-27T08:00:00Z"
        late = self.plan.write("epic-7: ready # go 2026-10-27")
        result = self.plan.read()
        self.assertEqual(result["state"], "NO_GO_RECORD")
        self.assertIn(f"the go commit {late[:12]} names no act of the owner and was committed by hand on 2026-10-27", result["reason"])
        # Before the cutover, but after a go bmn plan go recorded in the same history: nothing either.
        other = Plan()
        self.addCleanup(other.tmp.cleanup)
        other.write("epic-7: backlog", epic())
        approved = f"sha256:{run_needs.approval_text(run_needs.sections(epic()))}"
        recorded = other.write("epic-7: ready # go 2026-10-20", commit=self.go_message(approved))
        other.write("epic-7: backlog # withdrawn")
        other.write("epic-7: ready # go 2026-10-21")
        result = other.read()
        self.assertEqual(result["state"], "NO_GO_RECORD")
        self.assertIn(f"after {recorded[:7]}", result["reason"])

    def go_message(self, approved: str, source: str = "card 2026-10-26T09:30Z: owner answered 'Go'") -> str:
        return (f"plan: go for Epic 7 (go 2026-10-26)\n\nGo-Epic: 7\nGo-Date: 2026-10-26\nApproval-Source: {source}\n"
                f"Approved-Text: {approved}\nApproved-File: epics/007-fixture.md\n")

    def test_a_recorded_go_names_his_act_and_the_approved_text(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        approved = f"sha256:{run_needs.approval_text(run_needs.sections(epic()))}"
        go = self.plan.write("epic-7: ready # go 2026-10-26", commit=self.go_message(approved))
        result = self.plan.read()
        self.assertEqual((result["state"], result["go_commit"], result["provenance"], result["approved_text"]), ("GO", go, "recorded", approved))
        self.assertEqual(result["approval_source"], "card 2026-10-26T09:30Z: owner answered 'Go'")

    def test_a_go_whose_text_is_not_what_it_names_grants_nothing(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        self.plan.write("epic-7: ready # go 2026-10-26", commit=self.go_message("sha256:" + "0" * 64))
        result = self.plan.read()
        self.assertEqual(result["state"], "NO_GO_RECORD")
        self.assertIn("grants nothing", result["reason"])

    def test_an_older_go_without_a_record_stands_and_says_so(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        self.plan.write("epic-7: ready # go 2026-10-20")
        result = self.plan.read()
        self.assertEqual((result["state"], result["provenance"], result["approval_source"]), ("GO", "not recorded", None))

    def test_a_row_put_back_to_backlog_or_dropped_withdraws_the_go_and_a_pause_keeps_it(self) -> None:
        self.plan.write("epic-7: backlog", epic())
        self.plan.write("epic-7: ready # go 2026-10-20")
        self.plan.write("epic-7: paused # owner stopped")
        self.assertEqual(self.plan.read()["state"], "GO")
        for status in ("backlog", "dropped"):
            self.plan.write(f"epic-7: {status} # withdrawn", commit=None)
            result = self.plan.read()
            self.assertEqual((result["state"], result["withdrawn_go"]), ("NO_GO_RECORD", "2026-10-20"))

    def test_a_withdrawal_in_the_history_holds_until_his_next_go(self) -> None:
        # Astra review A2: ready/go, then put back and moved on without a new go, grants nothing.
        self.plan.write("epic-7: backlog", epic())
        self.plan.write("epic-7: ready # go 2026-10-20")
        withdrawn = self.plan.write("epic-7: backlog # withdrawn")
        self.plan.write("epic-7: in-progress # go 2026-10-20; run started anyway")
        result = self.plan.read()
        self.assertEqual((result["state"], result["withdrawn_go"]), ("NO_GO_RECORD", "2026-10-20"))
        self.assertIn(f"withdrawn at {withdrawn[:12]}", result["reason"])
        # A row taken off the board withdraws it too; a pause does not (the test above).
        removed = Plan()
        self.addCleanup(removed.tmp.cleanup)
        removed.write("epic-7: backlog", epic())
        removed.write("epic-7: ready # go 2026-10-20")
        (removed.root / "status.yaml").write_text(board("epic-8: backlog"))
        removed.write(commit="row removed")
        removed.write("epic-7: in-progress # go 2026-10-20")
        self.assertEqual(removed.read()["state"], "NO_GO_RECORD")
        # His next go stands again.
        self.plan.write("epic-7: ready # go 2026-10-21")
        result = self.plan.read()
        self.assertEqual((result["state"], result["go_date"]), ("GO", "2026-10-21"))

    def test_a_tracked_plan_reads_gos_and_withdrawals_where_he_records_them(self) -> None:
        # Astra review A2 variant: a linked worktree's tracked board is stale; the default checkout holds the withdrawal.
        main = self.plan.root.parent / "main"
        (main / "plan" / "epics").mkdir(parents=True)
        run = lambda where, *a: subprocess.run(["git", "-C", str(where), "-c", "user.name=F", "-c", "user.email=f@example.invalid", *a],
                                               check=True, capture_output=True, text=True,
                                               env={**os.environ, "GIT_COMMITTER_DATE": self.plan.date, "GIT_AUTHOR_DATE": self.plan.date}).stdout.strip()
        run(main, "init", "-qb", "main")
        (main / "plan" / "epics" / "007-fixture.md").write_text(epic())
        (main / "plan" / "status.yaml").write_text(board("epic-7: backlog"))
        run(main, "add", "-A"); run(main, "commit", "-qm", "docs: plan")
        (main / "plan" / "status.yaml").write_text(board("epic-7: ready # go 2026-10-20"))
        go = (run(main, "commit", "-qam", "docs: go"), run(main, "rev-parse", "HEAD"))[1]
        worktree = self.plan.root.parent / "run"
        run(main, "worktree", "add", "-q", "-b", "run", str(worktree))
        (main / "plan" / "status.yaml").write_text(board("epic-7: backlog # withdrawn"))
        status = {"ok": True, "format": "bmn-plan", "history": "product-repository", "tracked": True,
                  "plan_root": str(worktree / "plan"), "board": str(worktree / "plan" / "status.yaml"),
                  "board_checkout": str(worktree), "product_root": str(worktree), "default_checkout": str(main)}
        with mock.patch.object(run_needs, "resolve", return_value=status):
            self.assertEqual(run_needs.run_needs(worktree, 7)["state"], "NO_GO_RECORD")  # withdrawn on his board, not committed
            run(main, "commit", "-qam", "docs: withdraw")
            self.assertEqual(run_needs.run_needs(worktree, 7)["state"], "NO_GO_RECORD")  # committed on his branch only
            (main / "plan" / "status.yaml").write_text(board("epic-7: ready # go 2026-10-22"))
            again = (run(main, "commit", "-qam", "docs: go again"), run(main, "rev-parse", "HEAD"))[1]
            result = run_needs.run_needs(worktree, 7)
        self.assertEqual((result["state"], result["go_commit"]), ("GO", again))
        self.assertNotEqual(go, again)

    def test_a_second_recorded_go_on_the_same_day_is_a_new_go(self) -> None:
        # Astra review A3: bmn plan go again while ready on the same date, with new terms (a lower cap).
        self.plan.date = "2026-10-26T10:00:00Z"
        self.plan.write("epic-7: backlog", epic())
        first = self.plan.write("epic-7: ready # go 2026-10-26", commit=self.go_message(f"sha256:{run_needs.approval_text(run_needs.sections(epic()))}"))
        lower = epic(NEEDS.replace("$15", "$5"))
        self.plan.write(text=lower, commit="docs: lower the cap")
        source = "card 2026-10-26T11:00Z: owner answered 'Go, but only $5'"
        second = self.plan.write(commit=self.go_message(f"sha256:{run_needs.approval_text(run_needs.sections(lower))}", source))
        result = self.plan.read()
        self.assertEqual((result["state"], result["go_commit"], result["parsed"]["money_cap"]), ("GO", second, 5.0))
        self.assertEqual((result["approval_source"], result["earlier_gos"]), (source, [f"2026-10-26@{first[:12]}"]))

    def test_a_recorded_go_grants_only_with_its_whole_consistent_record(self) -> None:
        # Astra review A4: Approved-Text alone, or a source, epic, date or file that does not agree, grants nothing.
        approved = f"sha256:{run_needs.approval_text(run_needs.sections(epic()))}"
        good = self.go_message(approved)
        broken = {
            "only the approved text": f"plan: go\n\nApproved-Text: {approved}\n",
            "no source": good.replace("Approval-Source: card 2026-10-26T09:30Z: owner answered 'Go'\n", ""),
            "a source without his quoted words": good.replace("owner answered 'Go'", "owner answered Go"),
            "a source without a time": good.replace("card 2026-10-26T09:30Z", "card"),
            "a decision record as the source": good.replace("card 2026-10-26T09:30Z: owner answered 'Go'",
                                                            "bmn:01234567-89ab-cdef-0123-456789abcdef/dev-auto:run:d1 2026-10-26T09:30Z 'go'"),
            "another epic": good.replace("Go-Epic: 7", "Go-Epic: 8"),
            "another date": good.replace("Go-Date: 2026-10-26", "Go-Date: 2026-10-25"),
            "another file": good.replace("Approved-File: epics/007-fixture.md", "Approved-File: epics/008-other.md"),
        }
        for name, message in broken.items():
            plan = Plan()
            self.addCleanup(plan.tmp.cleanup)
            plan.write("epic-7: backlog", epic())
            plan.write("epic-7: ready # go 2026-10-26", commit=message)
            result = plan.read()
            self.assertEqual((result["state"], result.get("provenance")), ("NO_GO_RECORD", "incomplete"), name)
            self.assertIn("grants nothing", result["reason"], name)
        self.plan.write("epic-7: backlog", epic())
        self.plan.write("epic-7: ready # go 2026-10-26", commit=good)
        self.assertEqual(self.plan.read()["state"], "GO")

    def test_approval_text_matches_bmns_hash(self) -> None:
        # The same vector as BMN's plan-go.test.ts: bmn plan status and bmn plan go hash these bytes the same way.
        text = "# Epic 7: X\n\n## Run needs\n\n- **Money cap:** none.\n\n## Decisions\n\n- D1: yes.\n\n## Stories\n"
        self.assertEqual(run_needs.approval_text(run_needs.sections(text)), "99de4dc862fd74d97adc69107ab01cbb87ab8bfc454f560e6aa7d517e2c107bb")
        self.assertEqual(run_needs.approval_text(run_needs.sections("# Epic 7: X\n")),
                         run_needs.approval_text(run_needs.sections("# Epic 7: X\n\n## Run needs\n\n## Decisions\n")))

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
        self.assertIn("APPROVAL: not recorded with the go", printed)
        self.assertIn("**Extra repair rounds:** 2 per boundary.", printed)


if __name__ == "__main__":
    unittest.main()
