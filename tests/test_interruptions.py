# MODULE: test_interruptions.py - BMN Epic 96.2/96.7: one question counted once, the old count beside it, a bounded read-only count
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "dev-auto" / "scripts" / "interruptions.py"
sys.path.insert(0, str(SCRIPT.parent))
import interruptions  # noqa: E402

LEAD = "11111111-2222-4333-8444-555555555555"
OTHER = "99999999-2222-4333-8444-555555555555"
BMN_SESSION = "aaaaaaaa-2222-4333-8444-555555555555"


class CountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.db = root / "state.sqlite3"
        connection = sqlite3.connect(self.db)
        connection.execute("CREATE TABLE attention_request (request_id TEXT, session_id TEXT, request_key TEXT, kind TEXT, title TEXT, "
                           "body TEXT, opened_at TEXT, opened_by TEXT, prompt_json TEXT, producer_json TEXT)")
        connection.commit()
        connection.close()
        run = root / "run" / ".dev-auto"
        run.mkdir(parents=True)
        (run / "handoff.md").write_text(f"- Run id: epic7-20261026\n- Lead host / requested model / observed model: Claude Code (session {LEAD})\n"
                                        f"- Lead sessions: {LEAD}; BMN session {BMN_SESSION}\n- Status: ACTIVE\n")
        (run / "log.md").write_text("- 2026-10-26T09:00Z started\n- 2026-10-26T12:00Z still going\n")
        os.utime(run / "handoff.md", (1793017800, 1793017800))  # 2026-10-26T12:30Z
        self.handoff = run / "handoff.md"
        self.n = 0

    def add(self, opened: str, kind: str = "question", via: str = "hook:claude:PreToolUse", title: str = "Claude asks: Pick a fixture?",
            body: str = "", key: str = "claude:question", conversation: str = LEAD, generation: str = "g1", session: str = "s") -> str:
        self.n += 1
        request = f"{self.n:08x}-0000-4000-8000-000000000000"
        connection = sqlite3.connect(self.db)
        connection.execute("INSERT INTO attention_request VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (request, session, key, kind, title, body, f"2026-10-26T{opened}:00.000Z", via, "{}",
                            json.dumps({"conversationReference": conversation, "generation": generation})))
        connection.commit()
        connection.close()
        return request[:8]

    def run_count(self, seconds: float = 180) -> dict:
        return interruptions.count([self.handoff], self.db, seconds)["runs"][0]

    def test_a_mirror_with_its_cards_provenance_counts_once_and_the_old_count_counts_both(self) -> None:
        card = self.add("10:00", title="Claude has 2 questions: Epic 7 [n1]: GPU drawing? …", body="1. Epic 7 [n1]: GPU drawing? 2. Defer 7.2 AC3?")
        mirror = self.add("10:01", via="cli", title="Epic 7 [n1]: GPU drawing?", key="dev-auto-epic7-n1")
        run = self.run_count()
        self.assertEqual(run["old_count"]["total"], 2)
        self.assertEqual(run["corrected_count"]["questions_asked"], 1)
        self.assertEqual(run["corrected_count"]["mirrors_folded"], 1)
        self.assertIn({"request": mirror, "opened": "2026-10-26T10:01", "kind": "question", "class": "mirror", "mirror_of": card}, run["items"])

    def test_a_close_pair_without_provenance_stays_two_and_is_labelled(self) -> None:
        self.add("10:00", title="Claude asks: Restart now?")
        apart = self.add("10:01", via="cli", title="Epic 7 [n1]: GPU drawing?", key="dev-auto-epic7-n1")
        other_generation = self.add("10:01", via="cli", title="Restart now?", key="dev-auto-epic7-r", generation="g2")
        late = self.add("10:05", via="cli", title="Restart now?", key="dev-auto-epic7-r2")
        run = self.run_count()
        self.assertEqual(run["corrected_count"]["mirrors_folded"], 0)
        kept = {item["request"]: item for item in run["items"]}
        self.assertEqual(kept[apart]["possible_mirror_of"], kept[apart].get("possible_mirror_of"))
        self.assertIn("possible_mirror_of", kept[apart])
        self.assertIn("possible_mirror_of", kept[other_generation])
        self.assertNotIn("possible_mirror_of", kept[late])  # more than 120 s after the card
        self.assertEqual(run["corrected_count"]["possible_mirrors_kept"], 2)

    def test_a_matching_pair_without_a_generation_is_not_folded(self) -> None:
        # Astra review A7: equal empty generations are no provenance; the pair stays two, labelled a possible mirror.
        self.add("10:00", title="Claude has 2 questions: Epic 7 [n1]: GPU drawing? …", body="1. Epic 7 [n1]: GPU drawing?", generation="")
        mirror = self.add("10:01", via="cli", title="Epic 7 [n1]: GPU drawing?", key="dev-auto-epic7-n1", generation="")
        run = self.run_count()
        self.assertEqual((run["corrected_count"]["questions_asked"], run["corrected_count"]["mirrors_folded"]), (2, 0))
        self.assertIn("possible_mirror_of", {item["request"]: item for item in run["items"]}[mirror])

    def test_the_time_bound_holds_in_every_pass(self) -> None:
        # Astra review A7 and recheck R6: a deadline passed while the run is read, matched, classed or counted stops it there,
        # coverage partial, no traceback and no complete entry.
        for minute in range(10, 30):
            self.add(f"10:{minute}", title=f"Claude asks: Question {minute}?", body=f"1. Question {minute}?", generation=f"g{minute}")
            self.add(f"10:{minute}", via="cli", title=f"Question {minute}?", key=f"k{minute}", generation=f"g{minute}")
        self.assertTrue(self.run_count())  # the data is complete without a deadline
        for phase in ("read", "matched", "classed", "counted"):
            seen = {"read": 0}

            def past(deadline: float | None, where: str, phase: str = phase) -> bool:
                if where == "read":
                    seen["read"] += 1
                    return phase == "read" and seen["read"] > 1  # the check before the run passes; the read itself is late
                return where == phase
            with mock.patch.object(interruptions, "past", side_effect=past):
                result = interruptions.count([self.handoff], self.db, 3)
            self.assertFalse(result["complete"], phase)
            self.assertEqual(result["runs"], [{"handoff": str(self.handoff), "skipped": f"the time bound was reached while it was {phase}"}])

    def test_the_time_bound_holds_inside_the_query(self) -> None:
        # Astra review A7: the SQLite progress handler abandons a query once the deadline passes.
        for minute in range(10, 50):
            self.add(f"10:{minute}", via="cli", title=f"Question {minute}?", key=f"k{minute}")
        calls = iter(range(1, 1_000_000))  # call 1 sets the deadline, call 2 checks it before the run; later calls are past it
        with mock.patch.object(interruptions.time, "monotonic", side_effect=lambda: 100.0 if next(calls) > 2 else 0.0), \
                mock.patch.object(interruptions, "checked", side_effect=lambda items, deadline, phase: iter(items)):
            result = interruptions.count([self.handoff], self.db, 3)
        self.assertFalse(result["complete"])
        self.assertEqual(result["runs"][0]["skipped"], "the time bound was reached while it was read")

    def test_classes_repeats_and_permission_prompts(self) -> None:
        self.add("09:10", title="Claude asks: Merge PR 12 now?")
        self.add("09:20", title="Claude asks: Which option for the layout?")
        self.add("09:30", via="cli", title="Story 7.9: one look", key="dev-auto-epic7-20261026-look", conversation=OTHER)  # the run id is in its key
        self.add("09:40", via="cli", title="Story 7.9: one look", key="dev-auto-epic7-20261026-look-b", conversation=OTHER)
        self.add("09:50", title="Claude asks: Which option for the layout?")
        self.add("09:55", kind="permission", via="hook:claude:PermissionRequest", title="Claude wants to use Bash", key="claude:permission")
        self.add("10:00", title="Claude asks: something", conversation=OTHER)  # another conversation, no run key: not this run's
        self.add("08:00", title="Claude asks: before the run")  # before its time
        run = self.run_count()
        self.assertEqual(run["corrected_count"], {"questions_asked": 5, "owner-decision": 1, "plan-settleable": 1, "repeated": 2,
                                                  "unresolved": 1, "native-permission": 1, "mirrors_folded": 0, "possible_mirrors_kept": 0})
        self.assertEqual(run["old_count"], {"total": 6, "his": 0, "push": 1, "plan": 2, "unknown": 3})
        self.assertEqual(run["conversations"], 2)

    def test_a_question_in_the_runs_bmn_session_is_its_own(self) -> None:
        self.add("10:00", title="Claude asks: Pick a fixture?", conversation="", session=BMN_SESSION)
        self.assertEqual(self.run_count()["old_count"]["total"], 1)

    def test_the_time_bound_reports_partial_coverage_and_no_text_leaves_the_json(self) -> None:
        self.add("10:00", title="Claude asks: a private question text")
        result = interruptions.count([self.handoff, self.handoff], self.db, -1)
        self.assertFalse(result["complete"])
        self.assertEqual(result["runs"][0]["skipped"], "the time bound was reached first")
        done = subprocess.run([sys.executable, "-I", str(SCRIPT), str(self.handoff), "--db", str(self.db), "--json"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("private question", done.stdout)
        self.assertTrue(json.loads(done.stdout)["complete"])
        text = subprocess.run([sys.executable, "-I", str(SCRIPT), str(self.handoff), "--db", str(self.db)], capture_output=True, text=True).stdout
        self.assertIn("epic7-20261026: old count 1", text)
        self.assertIn("COVERAGE: complete", text)

    def test_the_database_is_opened_read_only(self) -> None:
        connection = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        with self.assertRaises(sqlite3.OperationalError):
            connection.execute("DELETE FROM attention_request")
        before = self.db.read_bytes()
        self.run_count()
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
