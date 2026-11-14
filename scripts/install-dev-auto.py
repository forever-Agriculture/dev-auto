#!/usr/bin/env python3
# MODULE: install-dev-auto.py - link shared skills and register the dev-auto recovery hook
"""Install or check the shared skill links and dev-auto's SessionStart recovery hook.

Links: Codex and Claude Code share ``skills/dev-auto`` from this checkout. ``skills/epic-lead-planning``
is no longer installed: planning is BMN's ``plan`` skill, which BMN installs itself.
Existing conflicting files or links are never overwritten.

Hooks (default; skip with ``--links-only``): one ``SessionStart`` group with matcher ``compact|resume``
running ``hooks/dev-auto-session-start.py`` is appended to
``~/.claude/settings.json`` and ``~/.codex/hooks.json``. Existing groups, order, and unrelated
keys are preserved; files are written atomically and read back. Codex still
requires trusting the new hook through ``/hooks``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "dev-auto"
SKILL_SOURCES = {"dev-auto": SOURCE}
HOOK_SCRIPT = ROOT / "hooks" / "dev-auto-session-start.py"
SKILL_DIRS = (Path(".agents/skills"), Path(".claude/skills"))
HOOK_FILES = (
    Path(".claude/settings.json"),
    Path(".codex/hooks.json"),
)
HOOK_EVENT = "SessionStart"
HOOK_MATCHER = "compact|resume"
HOOK_TIMEOUT = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="check links and hook registration without changing the filesystem",
    )
    parser.add_argument(
        "--links-only",
        action="store_true",
        help="install skill links but do not register the SessionStart hook",
    )
    parser.add_argument(
        "--target-root",
        type=Path,
        help="compose destinations below this directory instead of the real home",
    )
    return parser.parse_args()


def exists_or_link(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def matches(path: Path, source: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        return path.resolve(strict=True) == source
    except (OSError, RuntimeError):
        return False


def blocked_parent(path: Path) -> Path | None:
    parent = path.parent
    while not exists_or_link(parent):
        if parent == parent.parent:
            return None
        parent = parent.parent
    return None if parent.is_dir() else parent


def hook_group(script: Path) -> dict:
    return {
        "matcher": HOOK_MATCHER,
        "hooks": [
            {
                "type": "command",
                "command": f"python3 {shlex.quote(str(script))}",
                "timeout": HOOK_TIMEOUT,
            }
        ],
    }


def load_json(path: Path) -> dict | None:
    """Return the parsed object, ``{}`` for a missing file, or ``None`` when unusable.

    Unusable means unreadable, invalid JSON, or a shape the hook registration
    cannot extend safely (``hooks`` not an object, or the event not a list).
    """
    if not exists_or_link(path):
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict) or not isinstance(hooks.get(HOOK_EVENT, []), list):
        return None
    return data


def find_groups(data: dict, script: Path) -> list[dict]:
    """Return every SessionStart group whose command mentions our hook script name."""
    groups = data.get("hooks", {}).get(HOOK_EVENT, []) if isinstance(data.get("hooks"), dict) else []
    found = []
    for group in groups if isinstance(groups, list) else []:
        hooks = group.get("hooks") if isinstance(group, dict) else None
        for hook in hooks if isinstance(hooks, list) else []:
            if isinstance(hook, dict) and script.name in str(hook.get("command", "")):
                found.append(group)
                break
    return found


def hook_state(path: Path, script: Path) -> str:
    data = load_json(path)
    if data is None:
        return "UNREADABLE"
    groups = find_groups(data, script)
    if not groups:
        return "MISSING"
    if len(groups) == 1 and groups[0] == hook_group(script):
        return "OK"
    return "CONFLICT"


def write_atomic(path: Path, data: dict) -> None:
    """Replace the file atomically, writing through symlinks and keeping its mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.resolve()
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=target.name, suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    if json.loads(path.read_text(encoding="utf-8")) != data:
        raise RuntimeError(f"read-back mismatch: {path}")


def register_hook(path: Path, script: Path) -> None:
    data = load_json(path)
    assert data is not None
    hooks = data.setdefault("hooks", {})
    groups = hooks.setdefault(HOOK_EVENT, [])
    groups.append(hook_group(script))
    write_atomic(path, data)


def main() -> int:
    args = parse_args()
    for skill_source in SKILL_SOURCES.values():
        if not (skill_source / "SKILL.md").is_file():
            print(f"ERROR: canonical skill is incomplete: {skill_source}", file=sys.stderr)
            return 2
    sources = {name: path.resolve(strict=True) for name, path in SKILL_SOURCES.items()}
    if not HOOK_SCRIPT.is_file():
        print(f"ERROR: hook script missing: {HOOK_SCRIPT}", file=sys.stderr)
        return 2

    root = (args.target_root or Path.home()).expanduser().resolve()
    destinations = [
        (root / skill_dir / name, skill_source)
        for skill_dir in SKILL_DIRS
        for name, skill_source in sources.items()
    ]
    hook_files = [root / relative for relative in HOOK_FILES]

    problems: list[str] = []
    for destination, skill_source in destinations:
        if exists_or_link(destination) and not matches(destination, skill_source):
            problems.append(f"nonmatching destination exists: {destination}")
        elif not exists_or_link(destination):
            blocker = blocked_parent(destination)
            if blocker is not None:
                problems.append(f"parent path is not a directory: {blocker}")
    if not args.links_only:
        for hook_file in hook_files:
            blocker = blocked_parent(hook_file)
            if blocker is not None:
                problems.append(f"hook parent path is not a directory: {blocker}")
            state = hook_state(hook_file, HOOK_SCRIPT)
            if state in {"UNREADABLE", "CONFLICT"}:
                problems.append(f"hook file {state.lower()}: {hook_file}")

    if args.check:
        ok = True
        for destination, skill_source in destinations:
            linked = matches(destination, skill_source)
            ok = ok and linked
            print(f"{'OK' if linked else 'MISSING_OR_CONFLICT'}: {destination}")
        for hook_file in hook_files:
            state = hook_state(hook_file, HOOK_SCRIPT)
            ok = ok and state == "OK"
            print(f"HOOK {state}: {hook_file}")
        return 0 if ok else 1

    if problems:
        for problem in problems:
            print(f"REFUSED: {problem}", file=sys.stderr)
        print("Nothing changed.", file=sys.stderr)
        return 2

    for destination, skill_source in destinations:
        if matches(destination, skill_source):
            print(f"OK: {destination} already links to {skill_source}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(skill_source, destination, target_is_directory=True)
        print(f"LINKED: {destination} -> {skill_source}")

    if not args.links_only:
        for hook_file in hook_files:
            if hook_state(hook_file, HOOK_SCRIPT) == "OK":
                print(f"OK: hook already registered in {hook_file}")
                continue
            register_hook(hook_file, HOOK_SCRIPT)
            print(f"HOOKED: {hook_file} <- {HOOK_EVENT} [{HOOK_MATCHER}] {HOOK_SCRIPT}")
        print("Codex: run /hooks in Codex once to review and trust the new hook.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
