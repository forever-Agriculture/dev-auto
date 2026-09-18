#!/usr/bin/env python3
# MODULE: dev-auto-session-start.py - SessionStart hook that restores dev-auto run context after compaction or resume
"""Inject a dev-auto recovery reminder after context compaction or session resume.

Registered as a ``SessionStart`` hook (matcher ``compact|resume``) in Claude Code
and Codex. Reads the hook event from stdin, looks for ``.dev-auto/handoff.md``
in the session's working directory, and prints a bounded JSON
``additionalContext`` with the fixed reminder plus the handoff's key fields.
Silent when no run is recorded there or the run is COMPLETE. Fail-open: any
unexpected error produces no output and exit code 0. Never writes files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

SOURCES = {"compact", "resume"}
FIELD_LIMIT = 500
EXCERPT_LIMIT = 2_000
OMITTED = "(too long for this excerpt; read the handoff)"
FIELDS = (
    "Status",
    "Explicit user stop",
    "Restrictions and authorization boundaries",
    "Authorized provider routes",
    "Active native helpers",
    "Material pending findings",
    "Next safe action",
)
SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "dev-auto"

REMINDER = (
    "[dev-auto SessionStart hook, installed by the workstation owner via "
    "scripts/install-dev-auto.py; source: hooks/dev-auto-session-start.py] "
    "dev-auto run in progress; context was compacted or the session resumed. Before "
    "any other substantive action reread {skill} and {handoff}; before any dispatch "
    "reread {models}. The handoff, not memory, is authoritative for restrictions, "
    "authorized routes, explicit stops, pending findings, and active helpers. "
    "Continue the recorded next safe action; never restart completed or accepted "
    "work or duplicate an active helper. Keep your current role: this reminder "
    "starts no work and promotes no helper to lead. Current owner instructions "
    "override older records; missing authorization is not permission. An explicit "
    "user stop stays in force until the user asks to continue."
)


def parse_fields(text: str) -> dict[str, str]:
    """Return ``label -> value`` for top-level ``- Label: value`` bullets.

    A field's value continues over following lines until the next top-level
    bullet or heading, so indented continuation lines and indented sub-bullets
    stay attached; a non-indented ``- `` line starts a new field. Labels must
    not contain a colon; the first colon ends the label.
    """
    fields: dict[str, str] = {}
    label: str | None = None
    parts: list[str] = []

    def flush() -> None:
        if label is not None:
            fields[label] = "\n".join(parts).strip()

    for line in text.splitlines():
        if line.startswith("- ") and ":" in line:
            flush()
            head, _, rest = line[2:].partition(":")
            label, parts = head.strip(), [rest.strip()]
        elif line.startswith("#") or (line.startswith("- ") and label is not None):
            flush()
            label, parts = None, []
        elif label is not None:
            parts.append(line.rstrip())
    flush()
    return fields


def excerpt(fields: dict[str, str]) -> tuple[str, bool]:
    """Build the field excerpt, at most EXCERPT_LIMIT characters; the flag says whether anything was omitted."""
    lines: list[str] = []
    omitted = False
    for index, name in enumerate(FIELDS):
        value = next((v for k, v in fields.items() if k.startswith(name)), "").strip()
        if not value:
            continue
        candidate = f"- {name}: {value}"
        placeholder = f"- {name}: {OMITTED}"
        used = sum(len(line) + 1 for line in lines)
        reserve = sum(len(f"- {later}: {OMITTED}") + 1 for later in FIELDS[index + 1 :])
        if len(candidate) > FIELD_LIMIT or used + len(candidate) + reserve > EXCERPT_LIMIT:
            lines.append(placeholder)
            omitted = True
            continue
        lines.append(candidate)
    return "\n".join(lines), omitted


def build_context(cwd: Path) -> str | None:
    handoff = cwd / ".dev-auto" / "handoff.md"
    if not handoff.is_file():
        return None
    reminder = REMINDER.format(
        skill=SKILL_DIR / "SKILL.md",
        handoff=handoff,
        models=SKILL_DIR / "references" / "models.md",
    )
    try:
        fields = parse_fields(handoff.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return reminder + "\n\nHandoff excerpt unavailable; read the file directly."
    status_words = fields.get("Status", "").split()
    status = status_words[0].strip(".,;:!").upper() if status_words else ""
    if status == "COMPLETE":
        return None
    body, omitted = excerpt(fields)
    if not body:
        return reminder + "\n\nHandoff excerpt unavailable; read the file directly."
    note = "\n(Excerpt incomplete; the full handoff is required.)" if omitted else ""
    return f"{reminder}\n\nHandoff excerpt ({handoff}):\n{body}{note}"


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
        source = str(event.get("source") or "").lower()
        if source not in SOURCES:
            return 0
        cwd = Path(str(event.get("cwd") or os.getcwd()))
        context = build_context(cwd)
        if context is None:
            return 0
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            }
        }
        sys.stdout.write(json.dumps(output))
        sys.stdout.flush()
    except Exception:  # noqa: BLE001 - fail open by design
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
