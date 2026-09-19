#!/usr/bin/env python3
# MODULE: check.py - read-only acceptance lint and host receipt reader for dev-auto runs
"""Read-only helpers the lead runs by hand; nothing here writes, launches or decides.

check [PROJECT]     lint .dev-auto/handoff.md when Status is COMPLETE: placeholder
                    text in the model/usage fields, and raw evidence tracked by git.
usage PATH          print model, effort and usage from one Codex rollout (.jsonl)
                    or one Claude ``--output-format json`` receipt (.json).
usage --list PROJECT  list Codex rollouts whose session cwd is PROJECT; choose by hand.

Exit 0 PASS or SKIP (status not COMPLETE), 1 FAIL with one reason per line,
2 UNABLE when a required file or command cannot be read.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

PLACEHOLDERS = ("to be recorded", "tbd", "placeholder", "pending receipt",
                "from the codex rollout or claude receipt")
EMPTY_GAPS = re.compile(r";\s*gaps:\s*$")
FIELDS = ("Lead host / requested model / observed model", "Observed usage")
LARGE = 256 * 1024
SESSIONS = Path.home() / ".codex" / "sessions"


def find_handoff(start: Path) -> Path | None:
    start = start.resolve()
    for directory in (start, *start.parents):
        handoff = directory / ".dev-auto" / "handoff.md"
        if handoff.is_file():
            return handoff
        if (directory / ".git").exists() or directory == Path.home():
            return None
    return None


def field(body: str, name: str) -> str | None:
    prefix = f"- {name}:"
    for line in body.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def check(project: Path) -> int:
    handoff = find_handoff(project)
    if handoff is None:
        print(f"UNABLE: no .dev-auto/handoff.md at or above {project}")
        return 2
    body = handoff.read_text(encoding="utf-8", errors="replace")
    status = (field(body, "Status") or "").upper()
    if not status.startswith("COMPLETE"):
        print(f"SKIP: Status is {status or 'missing'}; completion checks apply only to COMPLETE")
        return 0
    failures = []
    for name in FIELDS:
        value = field(body, name)
        if not value:
            failures.append(f"'{name}' is empty")
        elif any(p in value.lower() for p in PLACEHOLDERS) or EMPTY_GAPS.search(value.lower()):
            failures.append(f"'{name}' still holds placeholder text: {value[:80]}")
    root = handoff.parent.parent
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", ".dev-auto"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"UNABLE: git ls-files failed in {root}: {exc}")
        return 2
    for rel in filter(None, out.split("\0")):
        path = root / rel
        size = path.stat().st_size if path.exists() else 0
        if rel.startswith(".dev-auto/evidence/") or rel.endswith(".jsonl") or (
                size > LARGE and rel != ".dev-auto/handoff.md"):
            failures.append(f"raw evidence tracked: {rel} ({size} bytes)")
    if failures:
        print(f"FAIL: {handoff}")
        for reason in failures:
            print(f"- {reason}")
        return 1
    print(f"PASS: {handoff}")
    return 0


def read_rollout(path: Path) -> dict:
    meta, routes, usage, first, last = {}, [], None, None, None
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            kind = record.get("type")
            stamp = record.get("timestamp")
            first, last = first or stamp, stamp or last
            if kind == "session_meta":
                meta = {k: payload.get(k) for k in ("id", "cwd", "cli_version", "originator")}
            elif kind == "turn_context":
                route = (payload.get("model") or "unavailable", payload.get("effort") or "unavailable")
                if route not in routes:
                    routes.append(route)
            elif kind == "event_msg" and payload.get("type") == "token_count":
                usage = (payload.get("info") or {}).get("total_token_usage") or usage
    return {"source": str(path), **meta, "first": first, "last": last,
            "routes": [f"{m}/{e}" for m, e in routes] or ["unavailable"],
            "total_token_usage": usage or "unavailable"}


def read_receipt(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    models = data.get("modelUsage") or {}
    return {"source": str(path), "models": list(models) or ["unavailable"],
            "usage": {m: {k: v for k, v in u.items() if k.endswith("Tokens") and k != "maxOutputTokens" or k == "costUSD"}
                      for m, u in models.items() if isinstance(u, dict)} or "unavailable",
            "total_cost_usd": data.get("total_cost_usd", "unavailable"),
            "num_turns": data.get("num_turns", "unavailable")}


def list_rollouts(project: Path) -> int:
    target = str(project.resolve())
    found = 0
    for path in sorted(SESSIONS.rglob("rollout-*.jsonl")):
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                head = json.loads(handle.readline() or "{}")
        except (OSError, ValueError):
            continue
        payload = head.get("payload") or {}
        if head.get("type") == "session_meta" and payload.get("cwd") == target:
            found += 1
            print(f"{head.get('timestamp')}  {payload.get('originator')}  {path}")
    print(f"{found} rollout(s) for {target}; pick the lead or helper session by hand")
    return 0


def usage(args: list[str]) -> int:
    if args[:1] == ["--list"] and len(args) == 2:
        return list_rollouts(Path(args[1]))
    if len(args) != 1:
        print("usage: check.py usage PATH | usage --list PROJECT")
        return 2
    path = Path(args[0])
    try:
        info = read_rollout(path) if path.suffix.lower() == ".jsonl" else read_receipt(path)
    except Exception as exc:  # any unreadable or malformed file is UNABLE, never a traceback
        print(f"UNABLE: cannot read {path}: {exc}")
        return 2
    print(json.dumps(info, indent=2))
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["check"] and len(argv) <= 2:
        return check(Path(argv[1]) if len(argv) == 2 else Path.cwd())
    if argv[:1] == ["usage"]:
        return usage(argv[1:])
    print((__doc__ or "").strip())
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
