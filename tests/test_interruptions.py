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
                           "body TEXT, opened_at TEXT, opened_by TEXT, prompt_json TEXT, producer_json TEXT, resolved_at TEXT)")
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
            body: str = "", key: str = "claude:question", conversation: str = LEAD, generation: str = "g1", session: str = "s", prompt: str = "{}") -> str:
        self.n += 1
        request = f"{self.n:08x}-0000-4000-8000-000000000000"
        connection = sqlite3.connect(self.db)
        connection.execute("INSERT INTO attention_request VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
                           (request, session, key, kind, title, body, f"2026-10-26T{opened}:00.000Z", via, prompt,
                            json.dumps({"conversationReference": conversation, "generation": generation})))
        connection.commit()
        connection.close()
        return request[:8]

    def run_count(self, seconds: float = 180) -> dict:
        return interruptions.count([self.handoff], self.db, seconds)["runs"][0]

    def hand_backs(self, *entries: tuple[str, str, str], dropped: int = 0) -> None:
        connection = sqlite3.connect(self.db)
        connection.execute("CREATE TABLE IF NOT EXISTS app_setting (key TEXT PRIMARY KEY, value_json TEXT)")
        rows = [{"at": f"2026-10-26T{at}:00.000Z", "sessionId": "s", "conversation": conversation, "agentCli": "claude", "outcome": outcome} for at, conversation, outcome in entries]
        connection.execute("INSERT OR REPLACE INTO app_setting VALUES ('question-hand-backs-v1', ?)", (json.dumps({"version": 1, "dropped": dropped, "entries": rows}),))
        connection.commit()
        connection.close()

    def resolve(self, request: str, at: str) -> None:
        connection = sqlite3.connect(self.db)
        connection.execute("UPDATE attention_request SET resolved_at = ? WHERE request_id LIKE ?", (f"2026-10-26T{at}:00.000Z", f"{request}%"))
        connection.commit()
        connection.close()

    def test_questions_by_their_reason_word_with_none_for_a_bare_one(self) -> None:
        self.add("10:00", title="Claude asks: Scope: drop the screen?")
        self.add("10:05", title="Claude asks: scope: drop the other screen?", generation="g2")
        self.add("10:10", via="cli", title="Go: ship it?", key="go-1", generation="g3")
        self.add("10:15", title="Claude asks: Which colour?", generation="g4")
        self.add("10:20", kind="permission", via="hook:claude:PermissionRequest", title="Claude wants to run git push")
        self.assertEqual(self.run_count()["reasons"], {"Scope": 2, "Go": 1, "none": 1})

    def test_each_question_of_a_batch_counts_under_its_own_word(self) -> None:
        questions = {"type": "questions", "questions": [{"text": "Scope: drop the screen?"}, {"text": "Money: pay for it?"}, {"text": "Which colour?"}]}
        self.add("10:00", title="Claude asks: Scope: drop the screen?", prompt=json.dumps(questions))
        self.assertEqual(self.run_count()["reasons"], {"Scope": 1, "Money": 1, "none": 1})

    def test_a_long_batch_is_read_whole_not_cut_at_a_permission_prompts_length(self) -> None:
        questions = {"type": "questions", "questions": [{"text": "Scope: " + "x" * 500}, {"text": "Go: ship it?"}]}
        self.add("10:00", title="Claude asks: Scope: x", prompt=json.dumps(questions))
        self.assertEqual(self.run_count()["reasons"], {"Scope": 1, "Go": 1})

    def test_a_prompt_that_is_not_questions_counts_by_its_title(self) -> None:
        self.add("10:00", title="Claude asks: Go: ship it?", prompt='{"type":"questions","questions":"nonsense"}')
        self.add("10:05", title="Go: ship the other?", via="cli", key="go-2", generation="g2", prompt="not json")
        self.assertEqual(self.run_count()["reasons"], {"Go": 2})

    def test_a_mirror_of_a_batch_is_folded_into_its_card(self) -> None:
        questions = {"type": "questions", "questions": [{"text": "Go: restart now?"}, {"text": "Money: pay?"}]}
        self.add("10:00", title="Claude asks: Go: restart now?", prompt=json.dumps(questions))
        self.add("10:00", via="cli", title="Go: restart now?", key="dev-auto-r")
        self.assertEqual(self.run_count()["reasons"], {"Go": 1, "Money": 1})

    def test_a_mirror_is_one_question_in_the_reason_count(self) -> None:
        self.add("10:00", title="Claude asks: Go: restart now?")
        self.add("10:00", via="cli", title="Go: restart now?", key="dev-auto-r")
        self.assertEqual(self.run_count()["reasons"], {"Go": 1})

    def test_hand_backs_and_repeats_of_this_run_only(self) -> None:
        self.hand_backs(("10:00", LEAD, "handed-back"), ("10:01", LEAD, "repeat"), ("10:02", LEAD, "handed-back"),
                        ("10:03", OTHER, "handed-back"), ("03:00", LEAD, "handed-back"))
        self.assertEqual(self.run_count()["hand_backs"], {"handed_back": 2, "repeated": 1, "readable": True, "may_have_lost": 0})

    def test_entries_dropped_from_before_what_is_kept_say_the_count_may_be_low(self) -> None:
        self.hand_backs(("10:30", LEAD, "handed-back"), dropped=7)
        run = self.run_count()
        self.assertEqual(run["hand_backs"], {"handed_back": 1, "repeated": 0, "readable": True, "may_have_lost": 7})

    def test_entries_dropped_before_the_run_began_lose_it_nothing(self) -> None:
        self.hand_backs(("03:00", OTHER, "handed-back"), ("10:30", LEAD, "handed-back"), dropped=7)
        self.assertEqual(self.run_count()["hand_backs"]["may_have_lost"], 0)

    def test_an_older_database_without_the_count_says_so_and_counts_the_rest(self) -> None:
        self.add("10:00", title="Claude asks: Go: restart now?")
        run = self.run_count()
        self.assertEqual(run["hand_backs"], {"handed_back": 0, "repeated": 0, "readable": False, "may_have_lost": 0})
        self.assertEqual(run["reasons"], {"Go": 1})

    def test_hours_native_prompts_held_and_those_over_thirty_minutes(self) -> None:
        one = self.add("10:00", kind="permission", via="hook:claude:PermissionRequest", title="git push")
        self.resolve(one, "11:30")
        two = self.add("11:00", kind="permission", via="hook:codex:PermissionRequest", title="something")
        self.resolve(two, "11:06")
        self.add("11:10", kind="permission", via="cli", title="a card is not a native prompt", key="card", generation="g5")
        self.assertEqual(self.run_count()["native_prompts"], {"count": 2, "over_30_minutes_at_most": 1, "hours_held_at_most": 1.6, "open": 0})

    def test_a_slow_command_counts_only_as_an_upper_bound_of_what_a_prompt_held(self) -> None:
        # Resolved at PostToolUse: approved at once, and the command then ran for two hours.
        one = self.add("10:00", kind="permission", via="hook:claude:PermissionRequest", title="pnpm run test")
        self.resolve(one, "12:00")
        found = self.run_count()["native_prompts"]
        self.assertEqual((found["hours_held_at_most"], found["over_30_minutes_at_most"]), (2.0, 1))
        self.assertNotIn("hours_held", found)

    def test_a_prompt_still_open_is_named_not_summed(self) -> None:
        self.add("10:00", kind="permission", via="hook:claude:PermissionRequest", title="git push")
        self.assertEqual(self.run_count()["native_prompts"], {"count": 1, "over_30_minutes_at_most": 0, "hours_held_at_most": 0.0, "open": 1})

    def test_the_words_a_person_reads(self) -> None:
        self.add("10:00", title="Claude asks: Go: restart now?")
        printed = subprocess.run([sys.executable, str(SCRIPT), str(self.handoff), "--db", str(self.db)], capture_output=True, text=True, check=True).stdout
        self.assertIn("reasons: Go 1", printed)
        self.assertIn("at most", printed)
        self.assertIn("handed back 0, repeated 0 (no count in this database)", printed)
        self.assertIn("native prompts 0, at most 0 over 30 minutes, at most 0.0 hours held, to the command's end", printed)

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
