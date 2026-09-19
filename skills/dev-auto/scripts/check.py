#!/usr/bin/env python3
# MODULE: check.py - read-only acceptance lint and host receipt reader for dev-auto runs
"""Read-only helpers the lead runs by hand; nothing here writes, launches or decides.

check [PROJECT]     lint .dev-auto/handoff.md. At any status: size within the recovery
                    hook's 9,000-character snapshot, exactly one Status, Explicit user
                    stop and Next safe action field, and a short Status. At COMPLETE also:
                    placeholder text in the model/usage fields, raw evidence tracked by
                    git, and dispatch rows that skip a work class's first tier without a reason.
usage PATH          print model, effort and usage from one Codex rollout (.jsonl),
                    one Claude Code session or subagent transcript (.jsonl under
                    ~/.claude/projects), or one Claude ``--output-format json``
                    receipt (.json).
usage --list PROJECT  list Codex rollouts whose session cwd is PROJECT; choose by hand.

Exit 0 PASS or SKIP (status not COMPLETE and shape checks pass), 1 FAIL with one reason per line,
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
# First-tier model per work class, from references/models.md. Rows are
# `purpose | class | model/effort | receipt | tier`; tier is `first` or `escalated: reason`.
FIRST_TIER = {"routine": "glm-5.3-flash", "complex": "glm-5.3", "debugging": "glm-5.3",
              "epic-review": "gpt-6-astra", "project-review": "gpt-6-astra"}
SESSIONS = Path.home() / ".codex" / "sessions"
SNAPSHOT_LIMIT = 9_000  # hooks/dev-auto-session-start.py injects the whole handoff up to this
STATUS_LIMIT = 200
FIELD_BLOCK = re.compile(r"^- ([^:\n]+):([^\n]*(?:\n(?!- |#)[^\n]*)*)", re.MULTILINE)
REQUIRED = (("Status", "Status"), ("Explicit user stop", r"Explicit user stop[^:\n]*"),
            ("Next safe action", "Next safe action"))


def find_handoff(start: Path) -> Path | None:
    start = start.resolve()
    for directory in (start, *start.parents):
        handoff = directory / ".dev-auto" / "handoff.md"
        if handoff.is_file():
            return handoff
        if (directory / ".git").exists() or directory == Path.home():
            return None
    return None


def dispatch_rows(body: str) -> list[str]:
    """Continuation rows under `- Dispatches:` until the next top-level field."""
    rows, inside = [], False
    for line in body.splitlines():
        if line.startswith("- Dispatches:"):
            inside = True
            continue
        if inside and (line.startswith("- ") or line.startswith("#")):
            break
        if inside and line.strip().startswith("- "):
            rows.append(line.strip()[2:])
    return rows


def lint_dispatches(body: str) -> list[str]:
    failures = []
    for row in dispatch_rows(body):
        parts = [p.strip() for p in row.split("|")]
        if len(parts) != 5:
            failures.append(f"dispatch row not in `purpose | class | model/effort | receipt | tier` form: {row[:80]}")
            continue
        _, work, route, _, tier = parts
        model = route.split("/")[0].strip().lower()
        first = FIRST_TIER.get(work.lower())
        if first is None:
            continue  # classes outside the table (lead, scout, consult) are not tiered
        if tier.lower() == "first" and model != first:
            failures.append(f"{work} dispatch marked first tier but used {route}; first tier is {first}")
        elif tier.lower().startswith("escalated"):
            if not tier.partition(":")[2].strip():
                failures.append(f"{work} dispatch escalated to {route} without a reason")
        elif tier.lower() != "first":
            failures.append(f"dispatch tier must be `first` or `escalated: reason`: {tier[:40]}")
    return failures


def shape(body: str) -> list[str]:
    """Checks that keep compaction recovery usable, whatever the status."""
    failures = []
    if len(body) > SNAPSHOT_LIMIT:
        failures.append(f"handoff is {len(body):,} characters; the recovery hook injects it whole "
                        f"only up to {SNAPSHOT_LIMIT:,}: move resolved history to a linked file")
    fields = [(m[1], m[2].strip()) for m in FIELD_BLOCK.finditer(body)]
    for label, pattern in REQUIRED:
        count = sum(1 for name, _ in fields if re.fullmatch(pattern, name))
        if count != 1:
            failures.append(f"expected one `- {label}:` field, found {count}")
    for name, value in fields:
        if name == "Status" and len(value) > STATUS_LIMIT:
            failures.append(f"Status is {len(value):,} characters; keep the label and a short reason "
                            f"(at most {STATUS_LIMIT}) and move details to their fields")
    return failures


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
    try:
        body = handoff.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"UNABLE: cannot read {handoff}: {exc}")
        return 2
    status = (field(body, "Status") or "").upper()
    failures = shape(body)
    if not status.startswith("COMPLETE"):
        if not failures:
            print(f"SKIP: Status is {status[:60] or 'missing'}; completion checks apply only to COMPLETE")
            return 0
        print(f"FAIL: {handoff}")
        for reason in failures:
            print(f"- {reason}")
        return 1
    for name in FIELDS:
        value = field(body, name)
        if not value:
            failures.append(f"'{name}' is empty")
        elif any(p in value.lower() for p in PLACEHOLDERS) or EMPTY_GAPS.search(value.lower()):
            failures.append(f"'{name}' still holds placeholder text: {value[:80]}")
    failures.extend(lint_dispatches(body))
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


USAGE_KEYS = {"input_tokens": "inputTokens", "output_tokens": "outputTokens",
              "cache_read_input_tokens": "cacheReadInputTokens",
              "cache_creation_input_tokens": "cacheCreationInputTokens"}


def is_codex_rollout(path: Path) -> bool:
    """A Codex rollout starts with a ``session_meta`` record; anything else is not one."""
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                return json.loads(line).get("type") == "session_meta"
            except (ValueError, AttributeError):
                return False
    return False


def read_claude_transcript(path: Path) -> dict:
    """One API response is written as several assistant lines sharing ``message.id``;
    the last line per id carries that response's final usage, so keep only that."""
    last_usage, routes, cost_state, first, last, session, cwd = {}, [], None, None, None, None, None
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            kind = record.get("type")
            if kind == "cost-state":
                cost_state = record
                continue
            if kind != "assistant":
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            stamp = record.get("timestamp")
            first, last = first or stamp, stamp or last
            session, cwd = session or record.get("sessionId"), cwd or record.get("cwd")
            model = message.get("model") or "unavailable"
            route = (model, record.get("effort") or "unavailable")
            if route not in routes:
                routes.append(route)
            usage = message.get("usage")
            if isinstance(usage, dict):
                last_usage[message.get("id") or record.get("uuid")] = (model, usage)
    totals: dict = {}
    for model, usage in last_usage.values():
        bucket = totals.setdefault(model, {v: 0 for v in USAGE_KEYS.values()})
        for key, name in USAGE_KEYS.items():
            value = usage.get(key)
            if isinstance(value, (int, float)):
                bucket[name] += value
    info = {"source": str(path), "id": session, "cwd": cwd, "first": first, "last": last,
            "routes": [f"{m}/{e}" for m, e in routes] or ["unavailable"],
            "responses": len(last_usage), "usage": totals or "unavailable"}
    if isinstance(cost_state, dict):
        info["session_cost_state"] = {
            "note": "cumulative for the whole session including native subagents",
            "total_cost_usd": cost_state.get("totalCostUSD", "unavailable"),
            "models": list(cost_state.get("modelUsage") or {}) or ["unavailable"]}
    return info


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
        if path.suffix.lower() != ".jsonl":
            info = read_receipt(path)
        elif is_codex_rollout(path):
            info = read_rollout(path)
        else:
            info = read_claude_transcript(path)
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
