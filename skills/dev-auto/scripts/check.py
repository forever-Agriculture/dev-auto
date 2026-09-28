#!/usr/bin/env python3
# MODULE: check.py - read-only acceptance lint and host receipt reader for dev-auto runs
"""Read-only helpers the lead runs by hand; nothing here writes, launches or decides.

check [PROJECT]     lint .dev-auto/handoff.md. At any status: size within the recovery
                    hook's 9,000-character snapshot, exactly one Status, Explicit user
                    stop and Next safe action field, a short Status, and `.dev-auto/`
                    ignored by git. At COMPLETE also: placeholder text in the observed
                    model and lead session fields. Tracked `.dev-auto` files are a NOTE:
                    removing them needs a repository change the owner approves.
usage PATH          print model, effort, Codex permission settings, timestamps, usage and
                    owner prompts from a rollout (.jsonl), one Claude Code session or
                    subagent transcript (.jsonl under ~/.claude/projects), or one Claude
                    ``--output-format json`` receipt (.json).
usage --list PROJECT  list Codex rollouts whose session cwd is PROJECT; choose by hand.

Exit 0 PASS or SKIP (status not COMPLETE and shape checks pass), 1 FAIL with one reason per line,
2 UNABLE when a required file or command cannot be read. ``-h`` or ``--help`` prints this text.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

PLACEHOLDERS = ("to be recorded", "tbd", "placeholder", "pending receipt",
                "from the codex rollout or claude receipt")
EMPTY_GAPS = re.compile(r";\s*gaps:\s*$")
FIELDS = ("Lead host / requested model / observed model", "Lead sessions")
# Run state is local to each checkout or worktree. Tracked state conflicted on every
# ProjectB epic PR, carried a stale handoff into main (2026-09-26..28) and put raw
# results in a company repository; old tracked files are a NOTE because a lead cannot
# remove them without a repository change (ProjectB 66 and 69 reported COMPLETE over a
# FAIL it could not fix). The exclude file is local and shared by every worktree.
EXCLUDE_HINT = 'echo .dev-auto/ >> "$(git rev-parse --git-path info/exclude)"'
GIT_ENV = {**os.environ, "LC_ALL": "C"}  # the not-a-repository test reads git's message
SESSIONS = Path.home() / ".codex" / "sessions"
SNAPSHOT_LIMIT = 9_000  # hooks/dev-auto-session-start.py injects the whole handoff up to this
STATUS_LIMIT = 200
FIELD_BLOCK = re.compile(r"^- ([^:\n]+):([^\n]*(?:\n(?!- |#)[^\n]*)*)", re.MULTILINE)
REQUIRED = (("Status", "Status"), ("Explicit user stop", r"Explicit user stop[^:\n]*"),
            ("Next safe action", "Next safe action"))
# The recovery hook's silence grammar (hooks/dev-auto-session-start.py): a run is
# finished only when the single Status is `COMPLETE` plus an optional note after
# punctuation, the single stop is `none` plus an optional note, and Status is the
# last line. A looser gate here let `COMPLETE pending acceptance` or a retained stop
# PASS while the hook kept waking every later session in the repository.
_NOTE = r"(?:[ \t]*[—–\-;:(.,!][^\n]*)?"
COMPLETE = re.compile(r"COMPLETE" + _NOTE, re.IGNORECASE)
NO_STOP = re.compile(r"none" + _NOTE, re.IGNORECASE)
TERMINAL = re.compile(r"-[ \t]*Status:[ \t]*" + COMPLETE.pattern, re.IGNORECASE)


def find_handoff(start: Path) -> Path | None:
    start = start.resolve()
    for directory in (start, *start.parents):
        handoff = directory / ".dev-auto" / "handoff.md"
        if handoff.is_file():
            return handoff
        if (directory / ".git").exists() or directory == Path.home():
            return None
    return None


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


def git_state(root: Path) -> tuple[list[str], list[str]] | None:
    """Failures and notes about run state in git; None when git cannot answer."""
    try:
        ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--no-index",
                                  ".dev-auto/handoff.md"], capture_output=True, text=True, env=GIT_ENV)
        if ignored.returncode == 128 and "not a git repository" in ignored.stderr:
            return [], []  # nothing here can be committed
        if ignored.returncode not in (0, 1):
            return None  # a broken repository or missing git is UNABLE, never a pass
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", ".dev-auto"],
                                 capture_output=True, text=True, check=True, env=GIT_ENV).stdout
        staged = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--name-only", "-z",
                                 "--diff-filter=d", "--", ".dev-auto"], capture_output=True,
                                text=True, check=True, env=GIT_ENV).stdout  # untracking is fine
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None
    failures = [] if ignored.returncode == 0 else [
        f"`.dev-auto/` is not ignored by git; run state stays local: {EXCLUDE_HINT}"]
    if staged.strip("\0"):  # `git add -A` or `commit -a` still stage files already tracked
        failures.append("run state is staged for commit: `git restore --staged -- .dev-auto`")
    names = list(filter(None, tracked.split("\0")))
    notes = [f"{len(names)} tracked .dev-auto file(s), e.g. {', '.join(names[:3])}: stage none of "
             "your changes to them; removing them needs a repository change the owner approves"] if names else []
    return failures, notes


def report(verdict: str, handoff: Path, failures: list[str], notes: list[str]) -> int:
    print(f"FAIL: {handoff}" if failures else verdict)
    for reason in failures:
        print(f"- {reason}")
    for note in notes:
        print(f"NOTE: {note}")
    return 1 if failures else 0


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
    state = git_state(handoff.parent.parent)
    if state is None:
        print(f"UNABLE: git cannot report on {handoff.parent}")
        return 2
    failures += state[0]
    if not status.startswith("COMPLETE"):
        return report(f"SKIP: Status is {status[:60] or 'missing'}; completion checks apply only to "
                      "COMPLETE", handoff, failures, state[1])
    fields = [(m[1], m[2].strip()) for m in FIELD_BLOCK.finditer(body)]
    statuses = [v for n, v in fields if n == "Status"]
    stops = [v for n, v in fields if re.fullmatch(REQUIRED[1][1], n)]
    if not (len(statuses) == 1 and COMPLETE.fullmatch(statuses[0])):
        failures.append("Status starts with COMPLETE but is not `COMPLETE` plus an optional note after "
                        "punctuation; a pending or paused state is its own label")
    if not (len(stops) == 1 and NO_STOP.fullmatch(stops[0])):
        failures.append("Explicit user stop must be `none` (plus an optional note after punctuation) at "
                        "COMPLETE; move stop history to .dev-auto/log.md")
    if not TERMINAL.fullmatch(body.rstrip().splitlines()[-1].strip() if body.strip() else ""):
        failures.append("`- Status: COMPLETE` must be the last line of the handoff so the recovery "
                        "hook stays silent")
    for name in FIELDS:
        value = field(body, name)
        if value is None:
            failures.append(f"'{name}' is missing; add `- {name}:` with its value")
        elif not value:
            failures.append(f"'{name}' is empty")
        elif any(p in value.lower() for p in PLACEHOLDERS) or EMPTY_GAPS.search(value.lower()):
            failures.append(f"'{name}' still holds placeholder text: {value[:80]}")
    return report(f"PASS: {handoff}", handoff, failures, state[1])


def read_rollout(path: Path) -> dict:
    meta, routes, usage, first, last = {}, [], None, None, None
    permissions, turns = [], 0
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
                policy = {k: payload.get(k) or "unavailable"
                          for k in ("sandbox_policy", "approval_policy")}
                if policy not in permissions:
                    permissions.append(policy)
            elif kind == "event_msg" and payload.get("type") == "token_count":
                usage = (payload.get("info") or {}).get("total_token_usage") or usage
            elif kind == "event_msg" and payload.get("type") == "task_started":
                turns += 1
    return {"source": str(path), **meta, "first": first, "last": last,
            "routes": [f"{m}/{e}" for m, e in routes] or ["unavailable"],
            "permissions": permissions or ["unavailable"],
            "total_token_usage": usage or "unavailable",
            "owner_turns": {"count": turns, "note": "turns started in this session; for an "
                            "interactive lead, about one per owner prompt"}}


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


def human(record: dict) -> bool:
    """Claude Code marks owner-typed messages `origin.kind: human`, both direct prompts and
    ones queued mid-turn; tool results, hook text and task notifications carry other marks.
    Handoffs undercounted owner touches in every run audited on 2026-09-28 (14 vs 3)."""
    kind = record.get("type")
    if kind == "attachment":
        record = record.get("attachment") or {}
        if record.get("type") != "queued_command":
            return False
    elif kind != "user":
        return False
    origin = record.get("origin")
    return isinstance(origin, dict) and origin.get("kind") == "human"


def read_claude_transcript(path: Path) -> dict:
    """One API response is written as several assistant lines sharing ``message.id``;
    the last line per id carries that response's final usage, so keep only that."""
    last_usage, routes, cost_state, first, last, session, cwd = {}, [], None, None, None, None, None
    prompts = 0
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
            if human(record):
                prompts += 1
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
            "responses": len(last_usage), "usage": totals or "unavailable",
            "owner_prompts": {"count": prompts, "note": "messages the host marked as typed by a "
                              "human, queued ones included; older transcripts may lack the mark"}}
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
        if not isinstance(head, dict):
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
    if {"-h", "--help"} & set(argv):  # `usage --help` once read as a path, and a lead
        print((__doc__ or "").strip())  # then recorded usage as unobservable
        return 0
    if argv[:1] == ["check"] and len(argv) <= 2:
        return check(Path(argv[1]) if len(argv) == 2 else Path.cwd())
    if argv[:1] == ["usage"]:
        return usage(argv[1:])
    print((__doc__ or "").strip())
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
