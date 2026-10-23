# MODULE: handoff_state.py - one completion grammar for recovery, lint and worktree offers
"""Keep continuation lines and duplicate fields when deciding whether a run finished."""
import re

READ_LIMIT = 1_000_000
FIELD_BLOCK = re.compile(r"^- ([^:\n]+):([^\n]*(?:\n(?!- |#)[^\n]*)*)", re.MULTILINE)
_NOTE = r"(?:[ \t]*[—–\-;:(.,!][^\n]*)?"
COMPLETE = re.compile(r"COMPLETE" + _NOTE, re.IGNORECASE)
NO_STOP = re.compile(r"none" + _NOTE, re.IGNORECASE)
TERMINAL = re.compile(r"-[ \t]*Status:[ \t]*" + COMPLETE.pattern, re.IGNORECASE)


def status_fields(body: str) -> tuple[list[str], list[str]]:
    fields = [(m[1], m[2].strip()) for m in FIELD_BLOCK.finditer(body)]
    return ([v for n, v in fields if n == "Status"],
            [v for n, v in fields if re.fullmatch(r"Explicit user stop[^:\n]*", n)])


def finished(body: str) -> bool:
    if len(body) > READ_LIMIT:
        return False
    statuses, stops = status_fields(body)
    terminal = body.rstrip().splitlines()[-1].strip() if body.strip() else ""
    return bool(len(statuses) == 1 and COMPLETE.fullmatch(statuses[0])
                and len(stops) == 1 and NO_STOP.fullmatch(stops[0])
                and TERMINAL.fullmatch(terminal))
