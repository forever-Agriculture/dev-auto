# MODULE: test_interruptions.py - BMN Epic 96.2/96.7: one question counted once, the old count beside it, a bounded read-only count
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
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

    def resolve(self, request: str, at: str) -> None:
        connection = sqlite3.connect(self.db)
        connection.execute("UPDATE attention_request SET resolved_at = ? WHERE request_id LIKE ?", (f"2026-10-26T{at}:00.000Z", f"{request}%"))
        connection.commit()
        connection.close()

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
        self.assertNotIn("reasons", printed)
        self.assertNotIn("handed back", printed)
        self.assertIn("phantoms 0, replaced 0, duplicates 0, repeated requests 0; rounds no ledger, step-backs no ledger", printed)
        self.assertIn("native waits 0, at most 0 over 30 minutes, at most 0.0 hours held, to the command's end", printed)
        self.assertIn("stories: no board; usage 0 asks, 0 in, 0 out, 2 lead sessions", printed)

    def test_two_cards_for_one_tool_call_are_a_phantom_asked_once(self) -> None:
        call = json.dumps({"toolUseId": "call-1"})
        first = self.add("10:00", title="Codex asks: Which colour?", via="hook:codex:PreToolUse", key="codex:question", prompt=call)
        self.add("10:00", title="Codex asks: Which colour?", via="hook:codex:PreToolUse", key="codex:question", prompt=call)
        run = self.run_count()
        self.assertEqual(run["corrected_count"]["phantom"], 1)
        self.assertEqual(run["corrected_count"]["questions_asked"], 1)
        self.assertEqual(run["items"][1]["same_card_as"], first)

    def test_a_card_replaced_in_its_slot_by_another_question_is_named_apart(self) -> None:
        self.add("10:00", title="Codex asks: Go: which colour?", via="hook:codex:PreToolUse", key="codex:question")
        self.add("10:00", title="Codex asks: Which colour?", via="hook:codex:PreToolUse", key="codex:question")
        run = self.run_count()["corrected_count"]
        self.assertEqual((run["phantom"], run["replaced"], run["questions_asked"]), (0, 1, 1))

    # Astra's full review, finding 5: the stored call id says which, a title and a time do not.
    def test_two_calls_with_one_title_in_a_slot_are_replaced_not_a_phantom(self) -> None:
        for name, prompts in (("different ids", ({"toolUseId": "call-1"}, {"toolUseId": "call-2"})), ("no ids", ({}, {})), ("one id", ({"toolUseId": "call-1"}, {}))):
            with self.subTest(name):
                self.setUp()
                for prompt in prompts:
                    self.add("10:00", title="Codex asks: Which colour?", via="hook:codex:PreToolUse", key="codex:question", prompt=json.dumps(prompt))
                run = self.run_count()["corrected_count"]
                self.assertEqual((run["phantom"], run["replaced"], run["questions_asked"]), (0, 1, 1))

    def test_one_call_id_in_two_slots_is_a_phantom_and_ids_of_other_sessions_are_apart(self) -> None:
        call = json.dumps({"toolUseId": "call-1"})
        self.add("10:00", title="Codex asks: Which colour?", key="codex:question", prompt=call)
        self.add("10:01", title="Codex asks: Which colour?", key="codex:question", prompt=call)
        self.add("10:02", title="Codex asks: Another?", key="codex:question", prompt=call, session="s2")
        run = self.run_count()["corrected_count"]
        self.assertEqual((run["phantom"], run["repeated"], run["questions_asked"]), (1, 0, 2))

    # Astra's recheck: a call that replaced a card keeps its identity.
    def test_a_replacing_call_seen_again_is_a_phantom(self) -> None:
        one, two = json.dumps({"toolUseId": "call-a"}), json.dumps({"toolUseId": "call-b"})
        self.add("10:00", title="Codex asks: First?", key="codex:question", prompt=one)
        second = self.add("10:00", title="Codex asks: Second?", key="codex:question", prompt=two)
        self.add("10:01", title="Codex asks: Second?", key="codex:question", prompt=two)
        run = self.run_count()
        self.assertEqual([item["class"] for item in run["items"]][1:], ["replaced", "phantom"])
        self.assertEqual(run["items"][2]["same_card_as"], second)

    def test_hook_runs_behind_one_card_are_stated_as_not_counted(self) -> None:
        # Two hook runs, one card (.dev-auto/evidence/106-19/sessions-after.json): the store shows one row, so the count says what it cannot see.
        self.add("10:00", title="Codex asks: Which colour?", key="codex:question", prompt=json.dumps({"toolUseId": "call-1"}))
        run = self.run_count()
        self.assertEqual(run["corrected_count"]["phantom"], 0)
        self.assertEqual(run["hook_records"]["kept"], False)
        self.assertIn("bmn hooks check", run["hook_records"]["coverage"])
        lines = self.printed()
        self.assertIn("extra hook runs behind one card: not counted", lines)

    def printed(self) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(interruptions.main([str(self.handoff), "--db", str(self.db)]), 0)
        return buffer.getvalue()

    def test_two_tool_calls_asking_the_same_within_a_minute_are_no_phantom(self) -> None:
        self.add("10:00", title="Codex asks: Which colour?", key="codex:question")
        self.add("10:01", title="Codex asks: Which colour?", key="codex:question")
        run = self.run_count()
        self.assertEqual(run["corrected_count"]["phantom"], 0)
        self.assertEqual(run["corrected_count"]["repeated"], 1)

    def test_the_same_instant_in_another_session_is_no_phantom(self) -> None:
        self.add("10:00", title="Codex asks: Which colour?", session="s1")
        self.add("10:00", title="Codex asks: Which colour?", session="s2")
        self.assertEqual(self.run_count()["corrected_count"]["phantom"], 0)

    def outcome_fixture(self, states: dict[str, str]) -> None:
        board = self.handoff.parent.parent / "plan" / "status.yaml"
        board.parent.mkdir()
        board.write_text("development_status:\n" + "".join(f"  {row}: {state}\n" for row, state in states.items()))
        text = self.handoff.read_text()
        self.handoff.write_text(text + f"- Board: bmn-plan, `{board}`\n- Budget: abcdef0123456789-epic-7\n")
        os.utime(self.handoff, (1793017800, 1793017800))

    def test_a_run_with_few_cards_and_most_stories_parked_is_no_success(self) -> None:
        self.outcome_fixture({"epic-7": "in-progress", "7-1-a": "done", "7-2-b": "blocked", "7-3-c": "paused", "7-4-d": "dropped", "8-1-other": "done"})
        with (self.handoff.with_name("log.md")).open("a") as log:
            log.write("- 2026-10-26T10:00Z parked 7.2 on its gate\n- 2026-10-26T11:30Z parked 7.3 on its gate\n- 2026-10-26T10:30Z unparked 7.9\n")
        os.utime(self.handoff, (1793017800, 1793017800))
        stories = self.run_count()["stories"]
        self.assertEqual(stories["done"], 1)
        self.assertEqual(stories["parked"], ["7.2", "7.3"])
        self.assertEqual(stories["counts_as_success"], False)
        self.assertEqual(stories["parked_hours"], 3.7, "from each parked line to the run's end plus the slack")

    def test_a_parked_story_with_no_log_line_is_named_not_counted_as_no_time(self) -> None:
        self.outcome_fixture({"7-1-a": "done", "7-2-b": "blocked"})
        stories = self.run_count()["stories"]
        self.assertEqual(stories["parked_hours"], 0.0)
        self.assertEqual(stories["parked_without_a_line"], ["7.2"])

    def test_the_board_and_ledger_come_from_bmn_when_the_handoff_names_neither(self) -> None:
        board = self.handoff.parent.parent / "plan" / "status.yaml"
        board.parent.mkdir()
        board.write_text("development_status:\n  7-1-a: done\n")
        text = self.handoff.read_text().replace("- Run id: epic7-20261026", "- Run id: run-1\n- Project / selected epics: x, Epic 7")
        self.handoff.write_text(text)
        os.utime(self.handoff, (1793017800, 1793017800))
        identity = hashlib.sha256(str(board.parent.resolve()).encode()).hexdigest()[:16]
        state = Path(self.tmp.name) / "state" / "dev-auto" / "budgets"
        state.mkdir(parents=True)
        (state / f"{identity}-epic-7.json").write_text(json.dumps({"rounds": {"a": {"answer": "TAKEN", "boundary": "7.1"}}}))
        with mock.patch.object(interruptions, "plan_of", return_value={"board": str(board), "plan_root": str(board.parent)}), mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(state.parents[1])}):
            run = self.run_count()
        self.assertEqual(run["stories"]["done"], 1)
        self.assertEqual(run["rounds"]["used"], 1)

    def test_a_story_unparked_counts_only_while_it_was_parked(self) -> None:
        self.outcome_fixture({"7-1-a": "done", "7-2-b": "done", "7-3-c": "blocked"})
        with (self.handoff.with_name("log.md")).open("a") as log:
            log.write("- 2026-10-26T09:00Z parked 7.2\n- 2026-10-26T10:00Z unparked 7.2\n")
        os.utime(self.handoff, (1793017800, 1793017800))
        stories = self.run_count()["stories"]
        self.assertEqual(stories["parked_hours"], 1.0)
        self.assertEqual(stories["counts_as_success"], True)

    def test_rounds_and_step_backs_come_from_the_ledger(self) -> None:
        self.outcome_fixture({"7-1-a": "done"})
        state = Path(self.tmp.name) / "state" / "dev-auto" / "budgets"
        state.mkdir(parents=True)
        (state / "abcdef0123456789-epic-7.json").write_text(json.dumps({"rounds": {
            "a": {"answer": "TAKEN", "boundary": "7.1"}, "b": {"answer": "TAKEN", "boundary": "7.1", "step_back": "2026"}, "c": {"answer": "REFUSED", "boundary": "7.1"}}}))
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(state.parents[1])}):
            self.assertEqual(self.run_count()["rounds"], {"used": 2, "step_backs": 1, "readable": True})

    def test_usage_adds_the_exported_asks_only(self) -> None:
        for name, tokens in (("a", 10), ("b", 5)):
            folder = self.handoff.with_name("evidence") / name
            folder.mkdir(parents=True)
            (folder / "outcome.json").write_text(json.dumps({"usage": {"input_tokens": tokens, "output_tokens": 1}}))
        self.assertEqual(self.run_count()["usage"], {"asks": 2, "input_tokens": 15, "output_tokens": 2, "lead_sessions": 2})

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

    # Astra's full review, finding 6: the new outcome collection keeps the bound.
    def name_nothing(self) -> None:
        text = self.handoff.read_text().replace("- Run id: epic7-20261026", "- Run id: run-1\n- Project / selected epics: x, Epic 7")
        self.handoff.write_text(text)
        os.utime(self.handoff, (1793017800, 1793017800))

    def test_asking_bmn_for_the_plan_gets_only_the_time_left(self) -> None:
        self.name_nothing()
        seen = []

        def run(argv, **options):
            seen.append(options["timeout"])
            return mock.Mock(returncode=1, stdout="")
        with mock.patch.object(interruptions.subprocess, "run", side_effect=run):
            interruptions.count([self.handoff], self.db, 2)
        self.assertTrue(seen)
        self.assertLessEqual(max(seen), 2)

    def test_a_hanging_bmn_ends_at_the_bound_as_partial_coverage(self) -> None:
        self.name_nothing()
        folder = Path(self.tmp.name) / "bin"
        folder.mkdir()
        (folder / "bmn").write_text("#!/bin/sh\nexec sleep 30\n")
        (folder / "bmn").chmod(0o755)
        started = time.monotonic()
        with mock.patch.dict(os.environ, {"PATH": f"{folder}:{os.environ['PATH']}"}):
            result = interruptions.count([self.handoff], self.db, 0.5)
        self.assertLess(time.monotonic() - started, 5)
        self.assertFalse(result["complete"])
        self.assertIn("outcomes", result["runs"][0]["skipped"])

    def test_the_plans_identity_gets_only_the_time_left(self) -> None:
        self.name_nothing()
        seen = {}

        def identity(root, timeout=10):
            seen["timeout"] = timeout
            return root
        with mock.patch.object(interruptions, "plan_of", return_value={"plan_root": "/nowhere"}), mock.patch.object(interruptions, "plan_identity", side_effect=identity):
            interruptions.count([self.handoff], self.db, 2)
        self.assertLessEqual(seen["timeout"], 2)

    def test_an_identity_cut_short_is_no_other_budget(self) -> None:
        self.name_nothing()

        def identity(root, timeout=10):
            interruptions.time.sleep(0.2)  # the bound ends here, and the ledger would fall back to the bare folder
            return root
        with mock.patch.object(interruptions, "plan_of", return_value={"plan_root": "/nowhere"}), mock.patch.object(interruptions, "plan_identity", side_effect=identity):
            result = interruptions.count([self.handoff], self.db, 0.1)
        self.assertFalse(result["complete"])
        self.assertIn("outcomes", result["runs"][0]["skipped"])

    def test_walking_the_evidence_stops_at_the_bound(self) -> None:
        evidence = self.handoff.with_name("evidence")
        for n in range(30):
            (evidence / f"a{n}").mkdir(parents=True)
        (evidence / "a0" / "outcome.json").write_text("{}")
        calls = {"n": 0}

        def past(deadline, where):
            if where != "outcomes":
                return False
            calls["n"] += 1
            return calls["n"] > 3
        with mock.patch.object(interruptions, "past", side_effect=past):
            result = interruptions.count([self.handoff], self.db, 3)
        self.assertFalse(result["complete"])
        self.assertIn("outcomes", result["runs"][0]["skipped"])
        self.assertLessEqual(calls["n"], 4)

    def test_the_ledgers_identity_takes_a_timeout_and_keeps_its_default(self) -> None:
        seen = []
        real = subprocess.run

        def run(argv, **options):
            seen.append(options["timeout"])
            return real(argv, **options)
        with mock.patch.object(subprocess, "run", side_effect=run):
            interruptions.plan_identity(self.tmp.name)
            interruptions.plan_identity(self.tmp.name, timeout=1.5)
        self.assertEqual(len(seen), 2)
        for observed, budget in zip(seen, (10, 1.5)):
            self.assertGreater(observed, 0)
            self.assertLessEqual(observed, budget)

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
                                                  "unresolved": 1, "native-permission": 1, "phantom": 0, "replaced": 0, "mirrors_folded": 0, "possible_mirrors_kept": 0})
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
