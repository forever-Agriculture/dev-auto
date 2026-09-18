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
            self.assertNotIn("Sprint board", context)
            self.assertLess(len(context), 3_000)

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

    def test_oversized_field_is_omitted_whole_and_marked(self) -> None:
        big = "never touch " + "x" * 700
        self.write_handoff(self.filled(**{"Restrictions and authorization boundaries": big}))
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertNotIn("x" * 50, context)
        self.assertIn("Restrictions and authorization boundaries: (too long", context)
        self.assertIn("Excerpt incomplete", context)

    def test_excerpt_total_stays_within_limit_with_many_large_fields(self) -> None:
        big = "x" * 430  # accepted lines reach ~1,950 chars, so the pre-fix placeholders overshoot
        self.write_handoff(self.filled(**{
            "Explicit user stop (if any; only a later user instruction clears it)": big,
            "Restrictions and authorization boundaries": big,
            "Authorized provider routes": big,
            "Active native helpers (ID, route, scope, ownership, state)": big,
            "Material pending findings": big,
            "Next safe action": big,
        }))
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        body = context.split("Handoff excerpt (", 1)[1].split("):\n", 1)[1]
        body = body.split("\n(Excerpt incomplete", 1)[0]
        self.assertLessEqual(len(body), 2_000, len(body))
        self.assertIn("(too long for this excerpt; read the handoff)", body)
        self.assertIn("Excerpt incomplete", context)

    def test_malformed_handoff_still_gives_reminder(self) -> None:
        self.write_handoff("garbage without any bullets\n")
        context = context_of(run_hook({"source": "compact", "cwd": str(self.root)}))
        self.assertIn("dev-auto run in progress", context)
        self.assertIn("Handoff excerpt unavailable", context)

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
