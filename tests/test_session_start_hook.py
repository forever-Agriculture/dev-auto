# MODULE: test_session_start_hook.py - deterministic checks for the dev-auto SessionStart recovery hook
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "dev-auto-session-start.py"
TEMPLATE = REPO / "skills" / "dev-auto" / "assets" / "handoff.md"


def run_hook(event: dict | str) -> subprocess.CompletedProcess[str]:
    payload = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def context_of(result: subprocess.CompletedProcess[str]) -> str:
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


class SessionStartHookTests(unittest.TestCase):
    def test_recovers_from_nested_directory(self) -> None:
        self.write_handoff(self.filled(**{'Material pending findings': 'F1 open'}))
        nested = self.root / 'src' / 'feature'
        nested.mkdir(parents=True)
        (self.root / '.git').mkdir()
        for source in ('compact', 'resume'):
            context = context_of(run_hook({'source': source, 'cwd': str(nested)}))
            self.assertIn(str(self.handoff), context)
            self.assertIn('F1 open', context)

    def test_does_not_cross_nested_repository_boundary(self) -> None:
        self.write_handoff(self.filled())
        nested = self.root / 'other-repo'
        nested.mkdir()
        # Worktrees use a .git file, not a directory.
        (nested / '.git').write_text('gitdir: elsewhere\n')
        result = run_hook({'source': 'resume', 'cwd': str(nested)})
        self.assertEqual((result.returncode, result.stdout), (0, ''))

    def test_nearest_completed_handoff_does_not_restore_parent_run(self) -> None:
        self.write_handoff(self.filled())
        nested = self.root / 'child'
        handoff = nested / '.dev-auto' / 'handoff.md'
        handoff.parent.mkdir(parents=True)
        handoff.write_text(self.filled().replace('- Status: ACTIVE', '- Status: COMPLETE'))
        result = run_hook({'source': 'resume', 'cwd': str(nested)})
        self.assertEqual((result.returncode, result.stdout), (0, ''))

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.handoff = self.root / ".dev-auto" / "handoff.md"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_handoff(self, text: str) -> None:
        self.handoff.parent.mkdir(parents=True, exist_ok=True)
        self.handoff.write_text(text, encoding="utf-8")

    def filled(self, **fields: str) -> str:
        text = TEMPLATE.read_text(encoding="utf-8")
        text = text.replace("- Status: ACTIVE | PAUSED | BLOCKED | COMPLETE", "- Status: ACTIVE")
        fields.setdefault("Explicit user stop (if any; only a later user instruction clears it)", "none")
        for label, value in fields.items():
            key = f"- {label}:"
            self.assertIn(key, text, label)
            text = text.replace(key, f"{key} {value}", 1)
        return text

    def test_silent_without_handoff(self) -> None:
        result = run_hook({"source": "compact", "cwd": str(self.root)})
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_silent_for_startup_and_clear(self) -> None:
        self.write_handoff(self.filled())
        for source in ("startup", "clear"):
            result = run_hook({"source": source, "cwd": str(self.root)})
            self.assertEqual((result.returncode, result.stdout), (0, ""), source)

    def test_silent_when_source_is_missing_or_unknown(self) -> None:
        self.write_handoff(self.filled())
        for event in ({"cwd": str(self.root)}, {"source": "", "cwd": str(self.root)}, {"source": "compaction", "cwd": str(self.root)}):
            result = run_hook(event)
            self.assertEqual((result.returncode, result.stdout), (0, ""), event)

    def test_complete_status_with_trailing_punctuation_is_silent(self) -> None:
        self.write_handoff(self.filled().replace("- Status: ACTIVE", "- Status: COMPLETE."))
        result = run_hook({"source": "compact", "cwd": str(self.root)})
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_complete_with_reason_and_cleared_stop_is_silent(self) -> None:
        # BMN Epic 14, 2026-09-20: the skill's own `COMPLETE — reason` and `none — note`
        # shapes woke an unrelated review session with a 9.8k "run in progress" injection.
        text = self.filled().replace(
            "- Status: ACTIVE", "- Status: COMPLETE — Epic 14 accepted at `00f5e38`: all suites green.",
        ).replace(
            "- Explicit user stop (if any; only a later user instruction clears it): none",
            "- Explicit user stop (if any; only a later user instruction clears it): none — the "
            "13:30 stop was cleared by the owner's `/dev-auto resume` (2026-09-20).",
        )
        self.assertIn("none — the", text)
        self.write_handoff(text)
        for source in ("compact", "resume"):
            result = run_hook({"source": source, "cwd": str(self.root)})
            self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_oversized_complete_handoff_is_silent(self) -> None:
        # ProjectB 2026-09-20: a 9,289-character COMPLETE handoff kept injecting the
        # INCOMPLETE warning into every later compaction in that repository.
        text = self.filled(**{"Implemented": "x" * 9_500}).replace(
            "- Status: ACTIVE", "- Status: COMPLETE — Epics 57 and 56 delivered.")
        self.assertGreater(len(text), 9_000)
        self.write_handoff(text)
        result = run_hook({"source": "compact", "cwd": str(self.root)})
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_file_beyond_read_cap_is_never_judged_complete(self) -> None:
        # Astra 2026-09-20: a COMPLETE-looking prefix must not hide state past the cap.
        text = ("- Explicit user stop: none\n- Status: COMPLETE\n" + "x" * 1_000_000
                + "\n- Status: ACTIVE\n")
        self.write_handoff(text)
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertIn("snapshot INCOMPLETE", context)
        self.assertIn("exceeds 1,000,000 characters", context)
        self.assertNotIn("x" * 50, context)

    def test_none_of_is_not_a_cleared_stop(self) -> None:
        text = self.filled().replace("- Status: ACTIVE", "- Status: COMPLETE").replace(
            "clears it): none", "clears it): none of the stops was lifted; owner said stop")
        self.assertIn("none of the stops", text)
        self.write_handoff(text)
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertIn("none of the stops", context)

    def test_silent_for_complete_run(self) -> None:
        self.write_handoff(self.filled().replace("- Status: ACTIVE", "- Status: COMPLETE"))
        result = run_hook({"source": "compact", "cwd": str(self.root)})
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_injects_reminder_paths_and_key_fields(self) -> None:
        self.write_handoff(self.filled(**{
            "Authorized provider routes": "Astra/medium only; never GLM",
            "Explicit user stop (if any; only a later user instruction clears it)": "",
            "Material pending findings": "F1 open: retry double-charges",
            "Next safe action": "run tests for story 2.3",
        }))
        for source in ("compact", "resume"):
            result = run_hook({"source": source, "cwd": str(self.root)})
            self.assertEqual(result.returncode, 0, result.stderr)
            context = context_of(result)
            self.assertIn(str(REPO / "skills" / "dev-auto" / "SKILL.md"), context)
            self.assertIn("before any dispatch, the skill's references/models.md", context)
            self.assertIn(str(self.handoff), context)
            self.assertIn("- Status: ACTIVE", context)
            self.assertIn("never GLM", context)
            self.assertIn("retry double-charges", context)
            self.assertIn("run tests for story 2.3", context)
            self.assertIn("Sprint board", context)
            self.assertLess(len(context), 14_000)

    def test_multiline_field_and_explicit_stop_are_kept_whole(self) -> None:
        text = self.filled().replace(
            "- Restrictions and authorization boundaries:",
            "- Restrictions and authorization boundaries: no production access\n"
            "  - never push\n  - local-only network",
        ).replace(
            "- Explicit user stop (if any; only a later user instruction clears it):",
            "- Explicit user stop (if any; only a later user instruction clears it): "
            "owner said stop at 14:02",
        )
        self.write_handoff(text)
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertIn("no production access\n  - never push\n  - local-only network", context)
        self.assertIn("owner said stop at 14:02", context)

    def test_renamed_fields_and_free_text_survive(self) -> None:
        text = ("# Handoff\n- Status: ACTIVE\n- Restrictions: never deploy\n"
                "- Provider routes: approved helper only\n- Risk 1: double charge\n"
                "Spend authorization: one attempt only; no replacement.\n"
                "- Restrictions: production access USED; no further access\n")
        self.write_handoff(text)
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertIn(text, context)
        self.assertIn("first tool action", context)

    def test_long_field_is_preserved_within_total_bound(self) -> None:
        text = self.filled(**{"Restrictions and authorization boundaries": "x" * 800})
        self.write_handoff(text)
        self.assertIn(text, context_of(run_hook({"source": "resume", "cwd": str(self.root)})))

    def test_oversized_handoff_is_omitted_whole_and_requires_trimming(self) -> None:
        # ProjectB 2026-09-19: "trim only if useful" left a 38k handoff untrimmed across 4 recoveries.
        text = "- Status: ACTIVE\n" + "x" * 9_000 + "\nNEVER SPEND AGAIN"
        self.write_handoff(text)
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertNotIn("x" * 50, context)
        self.assertIn("snapshot INCOMPLETE", context)
        self.assertIn("complete file before proceeding", context)
        self.assertIn("Trimming is required", context)
        self.assertIn(str(REPO / "skills" / "dev-auto" / "scripts" / "check.py") + " check", context)
        self.assertLess(len(context), 2_700)

    def test_exact_size_boundary_preserves_complete_text(self) -> None:
        text = "- Status: ACTIVE\n"
        text += "x" * (9_000 - len(text))
        self.write_handoff(text)
        self.assertIn(text, context_of(run_hook({"source": "compact", "cwd": str(self.root)})))

    def test_largest_handoff_fits_both_host_output_ceilings(self) -> None:
        # ProjectB 2026-09-19: an 8,597-character handoff plus the 1,426-character reminder
        # made 10,023 characters, and Claude Code injected only a 2 KB preview, after which
        # the lead skipped the required reread. Claude previews above 10,000 characters
        # (9,903 arrived whole on 2026-09-20); Codex keeps about 2,500 tokens.
        nested = self.root / ("p" * (80 - len(str(self.root)) - len("//.dev-auto/handoff.md")))
        self.handoff = nested / ".dev-auto" / "handoff.md"
        self.assertEqual(len(str(self.handoff)), 80)
        head = "- Status: ACTIVE\n"
        text = head + "x" * (9_000 - len(head))
        self.write_handoff(text)
        context = context_of(run_hook({"source": "compact", "cwd": str(nested)}))
        self.assertIn(text, context, "the reminder must leave room for a 9,000-character handoff")
        self.assertLessEqual(len(context), 9_950)
        # An ambiguous status adds its own warning; the budget still holds, with or without
        # the snapshot.
        self.write_handoff((head * 2 + "x" * (9_000 - 2 * len(head))))
        ambiguous = context_of(run_hook({"source": "compact", "cwd": str(nested)}))
        self.assertLessEqual(len(ambiguous), 9_950)
        self.assertIn("Status missing or ambiguous", ambiguous)

    def test_output_over_budget_falls_back_to_the_full_read_warning(self) -> None:
        # A very long project path must never produce a silently host-cut snapshot.
        nested = self.root / ("d" * 200)
        self.handoff = nested / ".dev-auto" / "handoff.md"
        self.write_handoff("- Status: ACTIVE\n" + "x" * 8_900)
        context = context_of(run_hook({"source": "resume", "cwd": str(nested)}))
        self.assertNotIn("x" * 50, context)
        self.assertIn("host budget", context)
        self.assertIn("Read the complete file before proceeding", context)
        self.assertLessEqual(len(context), 9_950)

    def test_ambiguous_complete_and_explicit_stop_are_not_suppressed(self) -> None:
        for text in ("- Status: ACTIVE\n- Status: COMPLETE\n",
                     "- Status: COMPLETE\n- Explicit user stop: stop now\n",
                     "- Explicit user stop:\n  owner says stop\n- Status: COMPLETE\n",
                     "- Status: COMPLETE pending acceptance\n",
                     "- Status: COMPLETE\n- Explicit user stop: none\n",  # GLM: Status must be last
                     "- Explicit user stop: none\n- Status: COMPLETE pending acceptance\n",
                     "- Explicit user stop: none but owner asked to pause\n- Status: COMPLETE\n",
                     # Astra 2026-09-20: a continuation line under a cleared stop is a stop.
                     "- Explicit user stop: none\n  - owner says stop\n- Status: COMPLETE\n",
                     "- Explicit user stop: none — cleared earlier\n  owner says stop again\n- Status: COMPLETE\n"):
            self.handoff.parent.mkdir(exist_ok=True)
            self.handoff.write_text(text)
            self.assertIn(text, context_of(run_hook({"source": "resume", "cwd": str(self.root)})))

    def test_malformed_handoff_still_gives_reminder(self) -> None:
        self.write_handoff("garbage without any bullets\n")
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertIn("dev-auto run in progress", context)
        self.assertIn("Status missing or ambiguous", context)

    def test_quoted_complete_or_missing_canonical_stop_still_injects(self) -> None:
        for text in ("- Explicit user stop: none\nExample:\n```\n- Status: COMPLETE\n```\n",
                     "- Stop: owner says stop\n- Status: COMPLETE\n",
                     "- Status: COMPLETE\n",
                     "- Explicit user stop: none\n- Explicit user stop: none\n- Status: COMPLETE\n"):
            self.handoff.parent.mkdir(exist_ok=True)
            self.handoff.write_text(text)
            self.assertIn(text, context_of(run_hook({"source": "resume", "cwd": str(self.root)})))

    def test_bad_input_fails_open(self) -> None:
        result = run_hook("{not json")
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_never_writes(self) -> None:
        self.write_handoff(self.filled())
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        run_hook({"source": "compact", "cwd": str(self.root)})
        after = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
