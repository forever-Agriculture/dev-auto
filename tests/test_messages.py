# MODULE: test_messages.py - BMN Story 106.8: Run needs name people and messages, and the ledger reserves each use before it is sent
from __future__ import annotations

import json
import os
from pathlib import Path
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
LINE = ("- **Messages:** under D4's limits, at most 2 per purpose per person: Dana, on the move PR's GitHub comments: asks for a review. "
        "Sam, Dana and Dan, in their chat threads: ask one access fact. "
        "each repository's owner (CODEOWNERS, else a reviewer; none: a draft for him), on that banner PR's comments: says it is comment-only. "
        "Live sessions: `bmn tell`, not counted.\n")


def text(messages: str = LINE) -> str:
    return test_run_needs.epic("- **Extra repair rounds:** 4 per boundary.\n- **Money cap:** none.\n- **Named actions for an Away card:** none.\n" + messages)


def go_message(body: str) -> str:
    approved = "sha256:" + run_needs.approval_text(run_needs.sections(body))
    return ("plan: go for Epic 7 (go 2026-10-23)\n\nGo-Epic: 7\nGo-Date: 2026-10-23\nApproval-Source: card 2026-10-23T09:00Z: 'Go'\n"
            f"Approved-Text: {approved}\nApproved-File: epics/007-fixture.md\n")


class Parsing(unittest.TestCase):
    def test_entries_are_read_with_person_destination_and_purpose(self) -> None:
        entries = run_needs.parse_needs(LINE)["messages"]
        self.assertEqual([e["people"] for e in entries], [["Dana"], ["Sam", "Dana", "Dan"], ["each repository's owner"]])
        self.assertEqual(entries[0]["destination"], "the move PR's GitHub comments")
        self.assertEqual(entries[1]["purpose"], "ask one access fact")
        self.assertEqual(entries[2]["destination"], "that banner PR's comments")

    def test_none_and_absent_name_no_one(self) -> None:
        self.assertEqual(run_needs.parse_needs("- **Messages:** none.\n")["messages"], [])
        self.assertEqual(run_needs.parse_needs("- **Money cap:** none.\n")["messages"], [])

    def test_person_is_a_prepared_kind(self) -> None:
        one = run_needs.parse_needs("- **Prepared:** person: Dana owns chat-service, check: his line in the org list, checked 2026-11-04.\n")["prepared"][0]
        self.assertEqual(one["kind"], "person")
        self.assertEqual(run_needs.prepared_problems([one]), [])


class Ledger(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "bin").mkdir()
        (self.root / "bin" / "bmn").write_text(f"#!/bin/sh\ncat '{self.root / 'status.json'}'\n")
        (self.root / "bin" / "bmn").chmod(0o755)
        patcher = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "state"), "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.plan = test_run_needs.Plan()
        self.addCleanup(self.plan.tmp.cleanup)
        body = text()
        self.plan.write("epic-7: backlog", body)
        self.plan.write("epic-7: ready # go 2026-10-23", commit=go_message(body))
        (self.root / "status.json").write_text(json.dumps(self.plan.status()))
        code, out = self.run_ledger("open", "--epic", "7", "--project", str(self.plan.root))
        self.assertEqual(code, 0, out)
        self.budget = out.split()[1].rstrip(":")

    def run_ledger(self, *argv: str) -> tuple[int, str]:
        done = subprocess.run([sys.executable, str(LEDGER), *argv], capture_output=True, text=True, env=os.environ.copy(), cwd=self.root)
        return done.returncode, done.stdout + done.stderr

    def reserve(self, use: str, text_hash: str, person: str = "Dana", destination: str = "the move PR's GitHub comments", purpose: str = "asks for a review") -> tuple[int, str]:
        return self.run_ledger("message", "reserve", "--budget", self.budget, "--use-id", use, "--person", person, "--destination", destination, "--purpose", purpose, "--text-hash", text_hash)

    def test_a_named_message_is_reserved_and_a_receipt_recorded(self) -> None:
        code, out = self.reserve("a", "h1")
        self.assertEqual(code, 0, out)
        self.assertIn("RESERVED", out)
        code, out = self.run_ledger("message", "sent", "--budget", self.budget, "--use-id", "a", "--receipt", "https://example.invalid/c/1")
        self.assertEqual(code, 0, out)
        _, listing = self.run_ledger("message", "list", "--budget", self.budget)
        self.assertIn("sent", listing)
        self.assertIn("https://example.invalid/c/1", listing)

    def test_someone_or_something_not_named_is_refused(self) -> None:
        self.assertEqual(self.reserve("a", "h", person="Art")[0], 1)
        self.assertEqual(self.reserve("b", "h", purpose="asks to merge")[0], 1)
        self.assertEqual(self.reserve("c", "h", destination="his email")[0], 1)

    def test_at_most_two_per_purpose_per_person_across_resumes(self) -> None:
        self.assertEqual(self.reserve("a", "h1")[0], 0)
        self.assertEqual(self.reserve("b", "h2")[0], 0)
        self.run_ledger("open", "--epic", "7", "--project", str(self.plan.root))  # a resume
        code, out = self.reserve("c", "h3")
        self.assertEqual(code, 1, out)
        self.assertIn("2", out)
        # Another person named for another purpose has their own count.
        self.assertEqual(self.reserve("d", "h4", person="Dan", destination="their chat threads", purpose="ask one access fact")[0], 0)

    def test_the_same_text_again_is_refused(self) -> None:
        self.assertEqual(self.reserve("a", "same")[0], 0)
        self.assertEqual(self.reserve("b", "same")[0], 1)

    def test_a_retry_answers_first_and_an_uncertain_send_stays_counted(self) -> None:
        self.assertEqual(self.reserve("a", "h1")[0], 0)
        self.assertEqual(self.reserve("a", "h1")[0], 0)  # the same use: one count
        self.assertEqual(self.reserve("b", "h2")[0], 0)
        _, listing = self.run_ledger("message", "list", "--budget", self.budget)
        self.assertIn("uncertain", listing)
        self.assertEqual(self.reserve("c", "h3")[0], 1)
        # Read the destination: it never arrived, so the use comes back, by that reading alone.
        self.assertEqual(self.run_ledger("message", "unsent", "--budget", self.budget, "--use-id", "a", "--read", "no such comment on the PR")[0], 0)
        self.assertEqual(self.reserve("c", "h3")[0], 0)

    def test_a_withdrawn_go_revokes_the_rest(self) -> None:
        self.assertEqual(self.reserve("a", "h1")[0], 0)
        self.plan.write("epic-7: backlog # put back")
        (self.root / "status.json").write_text(json.dumps(self.plan.status()))
        code, out = self.reserve("b", "h2")
        self.assertEqual(code, 1, out)
        self.assertIn("withdrawn", out)

    def test_group_owner_entry_takes_any_named_person(self) -> None:
        code, out = self.reserve("a", "h", person="Mia", destination="that banner PR's comments", purpose="says it is comment-only")
        self.assertEqual(code, 0, out)


class Words(unittest.TestCase):
    def test_the_skill_requires_saying_his_agent_wrote_it(self) -> None:
        skill = (REPO / "skills" / "dev-auto" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("spend_ledger.py message reserve", skill)
        self.assertIn("his agent wrote", skill)

    def test_the_review_brief_asks_whether_each_challenge_holds(self) -> None:
        self.assertIn("## Challenges", (REPO / "skills" / "dev-auto" / "references" / "review-brief.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
