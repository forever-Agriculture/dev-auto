#!/usr/bin/env python3
"""Install or check links to the canonical dev-auto skill without overwrites."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


SOURCE = Path(__file__).resolve().parents[1] / "skills" / "dev-auto"
DESTINATIONS = (
    Path(".agents/skills/dev-auto"),
    Path(".claude/skills/dev-auto"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="check both links without changing the filesystem",
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


def main() -> int:
    args = parse_args()
    source = SOURCE.resolve(strict=True)
    if not (source / "SKILL.md").is_file():
        print(f"ERROR: canonical skill is incomplete: {source}", file=sys.stderr)
        return 2

    root = (args.target_root or Path.home()).expanduser().resolve()
    destinations = tuple(root / relative for relative in DESTINATIONS)

    problems: list[str] = []
    for destination in destinations:
        if exists_or_link(destination) and not matches(destination, source):
            problems.append(f"nonmatching destination exists: {destination}")
        elif not exists_or_link(destination):
            blocker = blocked_parent(destination)
            if blocker is not None:
                problems.append(f"parent path is not a directory: {blocker}")

    if args.check:
        for destination in destinations:
            state = "OK" if matches(destination, source) else "MISSING_OR_CONFLICT"
            print(f"{state}: {destination}")
        return 0 if all(matches(path, source) for path in destinations) else 1

    if problems:
        for problem in problems:
            print(f"REFUSED: {problem}", file=sys.stderr)
        print("No links changed.", file=sys.stderr)
        return 2

    for destination in destinations:
        if matches(destination, source):
            print(f"OK: {destination} already links to {source}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(source, destination, target_is_directory=True)
        print(f"LINKED: {destination} -> {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
