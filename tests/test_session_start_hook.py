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
            self.assertIn(str(REPO / "skills" / "dev-auto" / "references" / "models.md"), context)
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

    def test_oversized_field_is_omitted_whole_never_clipped(self) -> None:
        text = "- Status: ACTIVE\n" + "x" * 12_000 + "\nNEVER SPEND AGAIN"
        self.write_handoff(text)
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertNotIn("x" * 50, context)
        self.assertNotIn("NEVER SPEND AGAIN", context)
        self.assertIn("snapshot INCOMPLETE", context)
        self.assertIn("complete file before proceeding", context)
        self.assertIn("- Status: [omitted whole, 12,035 characters", context)
        self.assertIn("no field found for: Explicit user stop, Restrictions, Next safe action", context)
        self.assertLess(len(context), 3_500)

    def test_oversized_handoff_injects_recovery_fields_excerpt(self) -> None:
        # Reproduces ProjectB 2026-09-19: a 38k handoff gave the recovered lead no content.
        text = self.filled(**{
            "Explicit user stop (if any; only a later user instruction clears it)": "stop after arm 6",
            "Restrictions and authorization boundaries": "no prod writes; cap $3",
            "Material pending findings": "F1 open\n" + "  - history line\n" * 900,
            "Next safe action": "rerun P4 offline",
        })
        self.assertGreater(len(text), 12_000)
        self.write_handoff(text)
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertIn("snapshot INCOMPLETE", context)
        self.assertIn(f"{len(text):,} characters", context)
        self.assertIn("check.py check", context)
        for kept in ("stop after arm 6", "no prod writes; cap $3", "- Status: ACTIVE", "rerun P4 offline"):
            self.assertIn(kept, context)
        self.assertNotIn("history line", context)
        self.assertLess(context.index("stop after arm 6"), context.index("no prod writes"))
        self.assertLess(len(context), 3_500)

    def test_excerpt_budget_keeps_stop_first_and_omits_later_fields_whole(self) -> None:
        text = ("- Restrictions: " + "r" * 5_500 + " NEVER PUSH\n"
                + "- Status: ACTIVE\n" + "- Log: " + "h" * 7_000 + "\n"
                + "- Explicit user stop: owner stop " + "s" * 900 + "\n")
        self.write_handoff(text)
        context = context_of(run_hook({"source": "resume", "cwd": str(self.root)}))
        self.assertIn("owner stop " + "s" * 900, context)
        self.assertIn("- Restrictions: [omitted whole, 5,527 characters", context)
        self.assertNotIn("r" * 50, context)
        self.assertNotIn("NEVER PUSH", context)
        self.assertIn("- Status: ACTIVE", context)
        self.assertNotIn("h" * 50, context)
        self.assertLess(len(context), 8_500)

    def test_exact_size_boundary_preserves_complete_text(self) -> None:
        text = "- Status: ACTIVE\n"
        text += "x" * (12_000 - len(text))
        self.write_handoff(text)
        self.assertIn(text, context_of(run_hook({"source": "compact", "cwd": str(self.root)})))

    def test_ambiguous_complete_and_explicit_stop_are_not_suppressed(self) -> None:
        for text in ("- Status: ACTIVE\n- Status: COMPLETE\n",
                     "- Status: COMPLETE\n- Explicit user stop: stop now\n",
                     "- Explicit user stop:\n  owner says stop\n- Status: COMPLETE\n",
                     "- Status: COMPLETE pending acceptance\n"):
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
