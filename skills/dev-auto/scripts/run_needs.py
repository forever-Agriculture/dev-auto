#!/usr/bin/env python3
# MODULE: run_needs.py - BMN Epic 90.3: the owner's go on an epic and the Run needs it approved, read from the plan's history
"""Name an epic's go and the Run needs and Decisions it approved, read-only.

Usage: run_needs.py EPIC [--project P] [--json]

The go is the approval event, not a later snapshot: the commit of the board in which the epic's row
changed to `ready` with `go YYYY-MM-DD` in its note, from a parent where the row had another status or
another go date, or a commit `bmn plan go` wrote for the epic (its Go-Epic trailer), however little the row
changed: a second go on the same day with new terms is a new go. A go date first committed while the row is
already past `ready` (the `ready` snapshot was never committed) grants nothing. A moved plan's BMAD-era go is the commit in which the row's dated `go`
comment appeared or changed. Later commits keeping the row keep the go; a new go date or a return to `ready` is a
reapproval, a new go, and what earlier gos let the run use stays used. A go recorded with `bmn plan go`
(BMN Epic 96.1) names in its commit message the epic (Go-Epic), the go date (Go-Date), the owner's act
(Approval-Source: his quoted words with their time), the SHA-256 of the Run needs and Decisions he approved
(Approved-Text) and the epic file (Approved-File); one missing any of them, or whose epic, date, file or text
at the commit differs, grants nothing, and an older go without any of them stands with its source unrecorded. A BMN-format go committed by hand
once `bmn plan go` records gos (from HAND_GO_CUTOVER, or after a go it recorded in the same history) names no
act of his and grants nothing. A row put back to `backlog` or `dropped` (or taken off the board) after the
go withdraws it, in a later commit or on the board now, until his next go; a board that cannot be read now
confirms no go. A plan the product repository
tracks is read in its default checkout, where gos are recorded and withdrawn, not in a linked worktree's copy.

An epic whose go's commit holds plan/allowances/N.yaml (BMN Epic 110) is read through `bmn plan allowances`, the
one parser of that file: the go's hash covers the file's text too, and its limits come from the go's version and
the last recorded `bmn plan allow` after it. A go whose commit holds none reads as before.

A project still on a BMAD board prints NEEDS_MOVE with the move `bmn plan status` names, and grants nothing:
dev-auto starts no run there (BMN Epic 108). A moved plan's earlier BMAD gos are still read from its history.

Prints one of GO, NO_GO_RECORD, NO_RUN_NEEDS or NEEDS_MOVE, then CHANGED_SINCE_GO when Run needs or Decisions differ
today from the go's commit (the run keeps the go's text and records the change for the owner). Exit 0;
2 only when the plan cannot be resolved (UNABLE).
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

GO_DATE = re.compile(r"\bgo (\d{4}-\d{2}-\d{2})\b")
# What `bmn plan go` takes as the owner's act (BMN plan-cli.mjs): his quoted words with their time, never a BMN decision record.
SOURCE_TIME = re.compile(r"\b(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}")
SOURCE_QUOTE = re.compile(r"[\"'“‘«][^\"'”’»]+[\"'”’»]")
DECISION_REFERENCE = re.compile(r"\bbmn: ?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/\S+")
WITHDRAWN = ("backlog", "dropped")
STORY = re.compile(r"^#{2,4} Story (\d+\.\d+)\b", re.M)
SECTIONS = ("Run needs", "Decisions")
# The day after `bmn plan go` was delivered (BMN Epic 96): a go without its recorded act committed from then grants nothing.
HAND_GO_CUTOVER = "2026-10-27"
# BMN Story 103.4's Prepared line: the kinds its template names.
PREPARED_KINDS = "account|credential|service|command|message|person|owner step"
PREPARED_NEED = re.compile(rf"^((?:{PREPARED_KINDS})(?:\s*,\s*(?:{PREPARED_KINDS}))*)\s*:\s*(.*)$", re.I | re.S)
NONE_BECAUSE = re.compile(r"^none\s*,?\s*because\s+(.+)$", re.I | re.S)
CHECKED_ON = re.compile(r"\bchecked\s+(\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))\b")
# One form with BMN's plan check (bin/plan-board.mjs PREPARED_LINE): a `-` or `*` mark or none; tests on both sides read one table.
PREPARED_LINE = re.compile(r"\s*(?:[-*]\s*)?\*\*prepared:?\*\*:?\s*(.*)", re.I)


def git(repo: Path, *args: str, timeout: float = 60) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip()[:200] or f"git {args[0]} failed")
    return done.stdout


def resolve(project: Path) -> dict:
    if shutil.which("bmn") is None:
        raise RuntimeError("no bmn command to resolve the plan")
    done = subprocess.run(["bmn", "plan", "status", "--json", "--project", str(project)],
                          capture_output=True, text=True, timeout=60)
    try:
        status = json.loads(done.stdout)
    except ValueError:
        raise RuntimeError(f"bmn plan status failed (exit {done.returncode}): {done.stderr.strip()[:200]}")
    if done.returncode != 0 or not status.get("ok", True):
        raise RuntimeError(f"bmn plan status: {status.get('code') or done.stderr.strip()[:200]}")
    return status


def row(board_text: str, epic: int) -> tuple[str, str] | None:
    match = re.search(rf"^ {{2}}epic-{epic}:[ \t]*([\w-]+)[ \t]*(?:#[ \t]?(.*?))?[ \t]*$", board_text, re.M)
    return (match.group(1), match.group(2) or "") if match else None


def retired_by_move(repo: Path, commit: str, board: str) -> bool:
    """Only a commit holding the move's record retired the board; any other deletion is an ordinary one."""
    try:
        return json.loads(git(repo, "show", f"{commit}:plan/migration.json")).get("source_board") == board
    except (RuntimeError, ValueError, AttributeError):
        return False


def find_gos(repo: Path, board: str, epic: int, bmad: bool, *, tip: str = "HEAD", after: str | None = None, initial_gos: list | None = None, initial_row: tuple | None = None, silent: frozenset[str] = frozenset()) -> tuple[list[dict], tuple[str, str] | None]:
    """Every go of the epic in the board's history, oldest first, each with the withdrawal that followed it; and the row at the last commit."""
    commits = git(repo, "log", "--reverse", "--format=%H", tip, "--", board).split()
    # A commit bmn plan go wrote names the epic in its message; it is a go even when the row's line did not change (96 Astra review).
    recorded = set() if bmad else set(git(repo, "log", "--format=%H", "-E", f"--grep=^Go-Epic: 0*{epic}[[:space:]]*$", tip).split())
    if recorded - set(commits):
        wanted = set(commits) | recorded
        commits = [commit for commit in git(repo, "rev-list", "--reverse", "--topo-order", tip).split() if commit in wanted]
    if after:
        preceding = set(git(repo, "rev-list", after).split())
        commits = [commit for commit in commits if commit not in preceding]
    gos, previous = [dict(go) for go in initial_gos or []], initial_row
    last_date = gos[-1]["date"] if gos else None
    for commit in commits:
        try:
            current = row(git(repo, "show", f"{commit}:{board}"), epic)
        except RuntimeError:
            if bmad and retired_by_move(repo, commit, board):
                continue  # A move retired the old board; a rollback restores it. Neither is a withdrawal.
            current = None  # the board was removed in this commit
        status, note = current or (None, "")
        match = GO_DATE.search(note)
        date = match.group(1) if match else None
        if commit in silent:
            # Reconciliation creates no approval, but it cannot conceal a withdrawal.
            if gos and "withdrawn" not in gos[-1] and (status is None or status in WITHDRAWN) and (previous is None or previous[0] not in WITHDRAWN):
                gos[-1]["withdrawn"] = {"commit": commit, "status": status or "off the board"}
            previous = (status, date) if current else None
            continue
        if bmad:
            new = date is not None and date != last_date
        else:
            # Only the move to ready with a dated go approves (90.3 AC1); a date first seen in a later status delegates nothing.
            new = commit in recorded or (status == "ready" and date is not None and (previous is None or previous[0] != "ready" or previous[1] != date))
        if new:
            gos.append({"date": date, "commit": commit, "status": status})
            last_date = date
        elif gos and "withdrawn" not in gos[-1] and (status is None or status in WITHDRAWN) and (previous is None or previous[0] not in WITHDRAWN):
            gos[-1]["withdrawn"] = {"commit": commit, "status": status or "off the board"}
        previous = (status, date) if current else None
    return gos, previous


def migration_origin(repo: Path, plan_root: Path, board_rel: str, *, deadline: float | None = None) -> dict | None:
    """The first committed move owns the source and history pin; working declarations cannot replace it."""
    deadline = time.monotonic() + 60 if deadline is None else deadline
    def read(*args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(["git", *args], 0)
        return git(repo, *args, timeout=remaining)
    header = (plan_root / "status.yaml").read_text() if (plan_root / "status.yaml").is_file() else ""
    moved = re.search(r"^moved_from:\s*([^\s#]+)", header, re.M)
    metadata_path = plan_root / "migration.json"
    metadata_rel = metadata_path.relative_to(repo).as_posix()
    origin = None
    try:
        # A recut supersedes the cut it merges: the committed declaration names which genuine move is current.
        current_head = json.loads(read("show", f"HEAD:{metadata_rel}")).get("history_head")
    except (RuntimeError, ValueError, AttributeError):
        current_head = None  # No committed declaration: every genuine move is a candidate, as before.
    # A recut merges the previous cut as its second parent; read each merge against its first parent so it counts as the move.
    for commit in read("log", "--reverse", "--topo-order", "--full-history", "--diff-merges=first-parent", "--no-patch", "--diff-filter=A", "--format=%H", "HEAD", "--", metadata_rel).split():
        try:
            recorded = json.loads(read("show", f"{commit}:{metadata_rel}"))
            source, anchor = recorded["source_board"], recorded["history_head"]
            committed = re.search(r"^moved_from:\s*([^\s#]+)", read("show", f"{commit}:{board_rel}"), re.M)
            if recorded.get("version") != 1 or not committed or committed.group(1) != source:
                continue
            if not isinstance(anchor, str) or not re.fullmatch(r"[0-9a-f]{40,64}", anchor) or read("rev-parse", f"{commit}^1").strip() != anchor:
                continue  # A publication projection is not the original cutover.
            if current_head is not None and anchor != current_head:
                continue  # An earlier cut the recut replaced.
            path = Path(source)
            if path.is_absolute() or any(part in (".", "..") for part in source.split("/")) or path.name != "sprint-status.yaml":
                continue
            origin = {"source_board": source, "history_head": anchor, "boundary": commit}
            local = json.loads(read("show", f"HEAD:{metadata_rel}")).get("local_history_head")
            if local is not None:
                # Local commits that stayed unpublished hold the gos the old reader saw; only the cutover commit may name them.
                named = read("log", "--reverse", "--first-parent", "--format=%H", "-G", "local_history_head", "HEAD", "--", metadata_rel).split()
                if not re.fullmatch(r"[0-9a-f]{40,64}", str(local)) or not named or read("rev-parse", f"{named[0]}^1").strip() != local or "Plan-Cutover: yes" not in read("log", "-1", "--format=%B", named[0]):
                    raise RuntimeError("the migration's local history cannot be confirmed")
                origin["local_history_head"] = local
            break
        except (ValueError, KeyError, TypeError):
            continue
        except RuntimeError as exc:
            if "local history" in str(exc):
                raise
            continue
    if origin is None:
        if moved or metadata_path.exists():
            raise RuntimeError("the migration has no confirmed committed cutover boundary")
        return None
    metadata = json.loads(metadata_path.read_text())
    if not isinstance(metadata, dict) or not moved or moved.group(1) != origin["source_board"] or metadata.get("version") != 1 or any(metadata.get(key) != origin[key] for key in ("source_board", "history_head")):
        raise RuntimeError("working migration declarations differ from the original committed move")
    return origin


def moved_gos(repo: Path, plan_root: Path, board_rel: str, epic: int, origin: dict) -> tuple[list[dict], tuple | None]:
    """A copied row or retirement of the old board is no approval event."""
    source, anchor, boundary = (origin[key] for key in ("source_board", "history_head", "boundary"))
    old, previous = find_gos(repo, source, epic, True, tip=origin.get("local_history_head") or anchor)
    old = [{**go, "bmad": True} for go in old]
    # Preserve the old reader's committed-status comparison through a status-word-only mapping.
    mapped = {"ready-for-dev": "ready", "superseded": "dropped", "withdrawn": "dropped", "skipped": "dropped", "deferred": "paused"}
    if previous:
        previous = (mapped.get(previous[0], previous[0]), previous[1])
    cutovers = frozenset(git(repo, "log", "--format=%H", "-E", "--grep=^Plan-Cutover: yes$", "HEAD").split())
    return find_gos(repo, board_rel, epic, False, after=boundary, initial_gos=old, initial_row=previous, silent=cutovers)


def sections(text: str | None) -> dict[str, str | None]:
    """The `## Run needs` and `## Decisions` sections (or `### ` ones in a BMAD epics file), their text without the heading."""
    out = {}
    for name in SECTIONS:
        match = re.search(rf"^(#{{2,4}}) {re.escape(name)}[ \t]*\n(.*?)(?=^#{{1,4}} |\Z)", text or "", re.M | re.S)
        out[name] = match.group(2).strip(" \t\r\n") if match else None
    return out


def approval_text(found: dict[str, str | None], allowances: str | None = None) -> str:
    """The SHA-256 a go names for its Run needs, Decisions and allowances file, if any; `bmn plan go` and `bmn plan status` hash them the same way."""
    text = f"Run needs\n{found['Run needs'] or ''}\nDecisions\n{found['Decisions'] or ''}\n"
    if allowances is not None:
        text += "Allowances\n" + allowances.replace("\r\n", "\n").replace("\r", "\n") + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def allowance_name(epic: int, names: list[str]) -> str | None:
    matching = [name for name in names if re.fullmatch(rf"0*{epic}\.yaml", name)]
    return matching[0] if len(matching) == 1 else None


def read_allowances(project: Path, epic: int, commit: str) -> dict:
    """What BMN reads of the file as of a go's commit (BMN D6): dev-auto keeps no parser of it."""
    done = subprocess.run(["bmn", "plan", "allowances", str(epic), "--json", "--at", commit, "--project", str(project)],
                          capture_output=True, text=True, timeout=60)
    try:
        read = json.loads(done.stdout)
    except ValueError:
        raise RuntimeError(f"bmn plan allowances failed (exit {done.returncode}): {done.stderr.strip()[:200]}")
    if done.returncode != 0 or not read.get("ok", True):
        raise RuntimeError(f"bmn plan allowances: {(read.get('error') or {}).get('code') or done.stderr.strip()[:200]}")
    return read


def hand_go_too_late(repo: Path, commit: str) -> str | None:
    """Why a BMN-format go without a recorded act grants nothing, or None when it predates `bmn plan go` (96 review)."""
    committed = git(repo, "log", "-1", "--format=%cs", commit).strip()
    if committed >= HAND_GO_CUTOVER:
        return f"committed by hand on {committed}, when gos are recorded with bmn plan go (from {HAND_GO_CUTOVER})"
    try:
        earlier = git(repo, "log", "-1", "--format=%h", "--grep=^Go-Epic: ", f"{commit}~1").strip()
    except RuntimeError:
        earlier = ""  # the go is the history's first commit
    return f"committed by hand after {earlier}, a go bmn plan go recorded in the same history" if earlier else None


def trailers(message: str) -> dict[str, str | None]:
    """What a `bmn plan go` commit names (96.1): epic, date, the owner's act, the approved text and file; all None for an older go."""
    def field(name: str) -> str | None:
        match = re.search(rf"^{name}: (.+)$", message, re.M)
        return match.group(1).strip() if match else None
    return {"epic": field("Go-Epic"), "date": field("Go-Date"), "source": field("Approval-Source"),
            "approved": field("Approved-Text"), "file": field("Approved-File")}


def record_gaps(recorded: dict, epic: int, go: dict, approved: str, file: str | None) -> list[str]:
    """What keeps a recorded go from granting: a missing or disagreeing part of its record (96 Astra review)."""
    source = recorded["source"] or ""
    gaps = [] if recorded["epic"] == str(epic) else [f"epic {recorded['epic'] or 'missing'}, not {epic}"]
    if recorded["date"] != go["date"] or go["status"] != "ready":
        gaps.append(f"go date {recorded['date'] or 'missing'} on a row {go['status'] or 'off the board'} with go {go['date'] or 'none'}")
    if not (SOURCE_QUOTE.search(source) and SOURCE_TIME.search(source)) or DECISION_REFERENCE.search(source):
        gaps.append("no owner's act (his quoted words with their time)" if source else "no Approval-Source")
    if recorded["approved"] != approved:
        gaps.append(f"approved text {(recorded['approved'] or 'missing')[:19]}…, not the Run needs and Decisions it holds")
    if file is None or recorded["file"] != file:
        gaps.append(f"approved file {recorded['file'] or 'missing'}, not {file or 'a single epic file'}")
    return gaps


def epic_name(epic: int, read) -> str | None:
    names = [name for name in read("epics") if re.fullmatch(rf"0*{epic}-[\w.-]+\.md", name)]
    return names[0] if len(names) == 1 else None


def epic_text_bmn(epic: int, read) -> str | None:
    name = epic_name(epic, read)
    return read(f"epics/{name}") if name else None


def epic_text_bmad(text: str | None, epic: int) -> str | None:
    match = re.search(rf"^(#{{1,3}}) Epic {epic}\b[^\n]*\n(.*?)(?=^\1 Epic \d|\Z)", text or "", re.M | re.S)
    return match.group(0) if match else None


def epic_text_platform(epic: int, names: list[str], read) -> str | None:
    """A BMAD project's epic kept in its own file, `docs/platform/epic-N-slug.md`, for an epics.md that only lists it (BMN 110.7).

    A story's file beside it (`epic-N-M-slug.md`) is not the epic's. The file with Run needs wins.
    """
    found = None
    for name in sorted(names):
        if not re.fullmatch(rf"docs/platform/epic-0*{epic}-(?!\d+-)[^/]*\.md", name):
            continue
        text = read(name)
        if sections(text)["Run needs"] is not None:
            return text
        found = found or text
    return found


def split_needs(value: str) -> list[str]:
    """A Prepared line's needs: split at each `;` outside backticks and parentheses, which a target or a command may hold."""
    parts, current, depth, quoted = [], "", 0, False
    for char in value:
        if char == "`":
            quoted = not quoted
        elif not quoted and char == "(":
            depth += 1
        elif not quoted and char == ")":
            depth = max(0, depth - 1)
        if char == ";" and not quoted and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    return [part.strip() for part in parts if part.strip()]


def parse_prepared(value: str) -> list[dict]:
    """BMN Story 103.5 AC1: `<kind>: <target>, check: <how>, checked <date>`, or kinds or the whole line `none, because <reason>`."""
    def need(kind: str | None, target: str | None = None, check: str | None = None, checked: str | None = None, because: str | None = None) -> dict:
        return {"kind": kind, "target": target, "check": check, "checked": checked, "none_because": because}
    whole = NONE_BECAUSE.match(value.strip())
    if whole:
        return [need(None, because=whole.group(1).strip().rstrip("."))]
    found = []
    for part in split_needs(value):
        named = PREPARED_NEED.match(part)
        if not named:
            found.append({**need(None, part.rstrip(".")), "unparsed": True})
            continue
        kinds, rest = [kind.strip() for kind in named.group(1).split(",")], named.group(2).strip()
        none = NONE_BECAUSE.match(rest)
        if none:
            found.extend(need(kind, because=none.group(1).strip().rstrip(".")) for kind in kinds)
            continue
        date = CHECKED_ON.search(rest)
        checked = date.group(1) if date else None
        check = re.search(r",?\s*\bcheck:\s*(.+?)(?=,\s*checked\s+\d{4}-\d{2}-\d{2}|\.?\s*$)", rest)
        cut = min(match.start() for match in (check, date) if match) if check or date else None
        target = (rest if cut is None else rest[:cut]).strip().rstrip(".,")
        found.extend(need(kind, target, check.group(1).strip() if check else None, checked) for kind in kinds)
    return found


def prepared_problems(found: list[dict]) -> list[str]:
    """What each parsed need lacks, in the words of BMN's plan check (R103-FR1): the lead reads them, and the run goes on."""
    problems = []
    for one in found:
        target = one["target"] or ""
        if one.get("unparsed"):
            problems.append(f'"{target[:60]}" is not <kind>: <target>, check: <how>, checked <date>')
        elif one["none_because"]:
            continue
        elif re.match(r"none\b", target, re.I):
            problems.append(f'{one["kind"]} says "{target}": say none, because <reason>')
        elif not target:
            problems.append(f'{one["kind"]} names no target')
        elif one["kind"] == "owner step":
            continue
        elif not one["check"]:
            problems.append(f'{one["kind"]}: {target[:40]} needs a check: how the run checks it')
        elif not one["checked"]:
            problems.append(f'{one["kind"]}: {target[:40]} needs a date: checked YYYY-MM-DD')
    return problems


def parse_messages(value: str) -> list[dict]:
    """`<person>, <on|in|by|via> <destination>: <purpose>`, sentence by sentence (BMN D4); a line without a destination, such as `bmn tell`, names no message."""
    value = re.sub(r"^.*?\bper person:\s*", "", value)
    entries = []
    for sentence in re.split(r"(?<=\.)\s+", value):
        match = re.match(r"^(.+?), ((?:on|in|by|via) .+?): (.+?)\.?$", sentence.strip())
        if match:
            people = [p.strip() for p in re.split(r",\s*|\s+and\s+", match.group(1))] if "(" not in match.group(1) else [match.group(1).split(" (")[0].strip()]
            entries.append({"people": people, "destination": re.sub(r"^(?:on|in|by|via) ", "", match.group(2)), "purpose": match.group(3)})
    return entries


def parse_needs(text: str | None) -> dict:
    needs = {"rounds": 0, "deferrable": [], "money_cap": None, "named_actions": None, "prepared": [], "messages": []}
    seen_prepared = False
    for line in (text or "").splitlines():
        prepared = PREPARED_LINE.fullmatch(line.rstrip())
        if prepared:
            # The first line of the section, as BMN's plan check reads it.
            if not seen_prepared:
                needs["prepared"], seen_prepared = parse_prepared(prepared.group(1).strip()), True
            continue
        item = re.match(r"\s*-\s*\*\*([^*]+?):?\*\*:?\s*(.*)", line)
        if not item:
            continue
        name, value = item.group(1).lower(), item.group(2).strip()
        if "repair round" in name:
            number = re.search(r"\d+", value)
            needs["rounds"] = int(number.group(0)) if number else 0
        elif "deferrable" in name:
            needs["deferrable"] = [] if value.lower().startswith("none") else [value]
        elif "money cap" in name:
            amount = re.search(r"\$\s?(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s?(?:USD|dollars)", value)
            needs["money_cap"] = None if value.lower().startswith("none") or not amount else float(amount.group(1) or amount.group(2))
        elif name == "messages":
            needs["messages"] = [] if value.lower().startswith("none") else parse_messages(value)
        elif "named action" in name:
            needs["named_actions"] = None if value.lower().startswith("none") else value
    return needs


def recorded_needs(project: Path, epic: int) -> dict:
    status = resolve(project)
    board = Path(status["board"])
    bmad = status.get("format") == "bmad"
    repo = Path(status.get("board_checkout") or status["product_root"])
    plan_root = Path(status.get("plan_root") or repo)
    default = Path(status.get("default_checkout") or repo)
    if status.get("history") == "product-repository" and default != repo:
        # Gos are recorded and withdrawn in the default checkout; a linked worktree's tracked copy can be stale (96 Astra review).
        board, plan_root, repo = default / board.relative_to(repo), default / plan_root.relative_to(repo), default
    if status.get("history") == "plan-repository":
        repo = plan_root
    prefix = "" if plan_root == repo else plan_root.relative_to(repo).as_posix() + "/"
    identity = {"plan_root": str(plan_root), "epic": epic, "format": status.get("format"), "history_repo": str(repo)}
    if bmad:
        # BMN and dev-auto no longer run a BMAD plan (BMN 108.6): it reads, and names the move.
        move = status.get("needs_move") or f"{board} is a BMAD board; BMN no longer writes it or runs it. Move the plan first (BMN docs/planning.md, \"Moving a BMAD plan safely\")"
        return {**identity, "state": "NEEDS_MOVE", "unconfirmed": True, "reason": move}
    if epic in status.get("conflicts", []):
        return {**identity, "state": "PLAN_CONFLICT", "unconfirmed": True, "reason": "local and upstream plan values conflict; both are kept in the Git publication journal; this epic grants nothing"}
    if status.get("authority_unconfirmed"):
        return {**identity, "state": "NO_GO_RECORD", "unconfirmed": True, "reason": "publication authority journal cannot be confirmed; this plan grants nothing until it is readable"}
    if status.get("default_available") is False:
        return {**identity, "state": "NO_GO_RECORD", "unconfirmed": True, "reason": "NO_DEFAULT_CHECKOUT: canonical approval history cannot be confirmed"}
    board_rel = board.relative_to(repo).as_posix()

    def current_read(path: str):
        target = plan_root / path
        return sorted(p.name for p in target.iterdir()) if target.is_dir() else target.read_text(encoding="utf-8", errors="replace")

    def epic_now() -> str | None:
        try:
            return epic_text_bmn(epic, current_read)
        except OSError:
            return None

    text_now = epic_now()
    legacy = bool(re.search(r"^<!--\s*bmn-plan:\s*bmad-legacy\b", text_now or "", re.M))
    try:
        origin = migration_origin(repo, plan_root, board_rel) if board.is_file() else None
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {**identity, "state": "NO_GO_RECORD", "unconfirmed": True, "reason": f"migration origin cannot be read or confirmed: {exc}"}
    moved = origin is not None
    now = sections(text_now)
    # The default rounds (BMN D19): where no go was ever recorded, or his go stands; never where one was withdrawn or cannot be confirmed.
    floor = {"floor": True, "stories": STORY.findall(text_now or "")}
    try:
        gos, committed_row = moved_gos(repo, plan_root, board_rel, epic, origin) if moved else find_gos(repo, board_rel, epic, False)
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        if moved:
            return {**identity, "state": "NO_GO_RECORD", "unconfirmed": True, "reason": f"old approval history cannot be confirmed: {exc}"}
        if now["Run needs"] is None:
            return {**identity, "state": "NO_RUN_NEEDS", "reason": "the epic has no Run needs"}
        return {**identity, "state": "NO_GO_RECORD", "reason": f"the board's history cannot be read: {exc}"}
    if not gos:
        if legacy:
            return {**identity, "state": "NEEDS_NORMALIZE", "reason": "unfinished legacy work has no confirmed historical Go; normalize its contract before a new Go"}
        board_now = row(board.read_text(encoding="utf-8", errors="replace"), epic) if board.exists() else None
        floor["row_status"] = board_now[0] if board_now else None
        if now["Run needs"] is None:
            return {**identity, **floor, "state": "NO_RUN_NEEDS", "reason": "the epic has no Run needs"}
        result = {**identity, **floor, "state": "NO_GO_RECORD", "reason": "no commit records a go for this epic"}
        date_now = GO_DATE.search(board_now[1]) if board_now else None
        if date_now:  # evidence that explains the gap; it grants nothing (96.2 AC5)
            result["uncommitted_go"] = date_now.group(1)
        return result
    go = gos[-1]

    def read_in(commit: str, path: str):
        if path == "epics":
            return git(repo, "ls-tree", "--name-only", f"{commit}:{prefix}epics").split()
        return git(repo, "show", f"{commit}:{prefix}{path}")

    def text_at(commit: str) -> str | None:
        """The epic's text as a go's commit holds it."""
        if any(g["commit"] == commit and g.get("bmad") for g in gos):
            found = None
            paths = git(repo, "ls-tree", "-r", "--name-only", commit).split()
            for path in paths:
                if path.endswith(".md") and "planning-artifacts" in path:
                    found = epic_text_bmad(git(repo, "show", f"{commit}:{path}"), epic) or found
            if sections(found)["Run needs"] is not None:
                return found
            return epic_text_platform(epic, paths, lambda path: git(repo, "show", f"{commit}:{path}")) or found
        try:
            return epic_text_bmn(epic, lambda path: read_in(commit, path))
        except RuntimeError:
            return None

    def allowances_at(commit: str) -> str | None:
        """The text of the epic's allowances file as a go's commit holds it (BMN D7), or None."""
        if any(g["commit"] == commit and g.get("bmad") for g in gos):
            return None
        try:
            name = allowance_name(epic, git(repo, "ls-tree", "--name-only", f"{commit}:{prefix}allowances").split())
            return read_in(commit, f"allowances/{name}") if name else None
        except RuntimeError:
            return None

    then_text = text_at(go["commit"])
    then = sections(then_text)
    then_allowances = allowances_at(go["commit"])
    changed = [name for name in SECTIONS if (then[name] or "") != (now[name] or "")]
    result = {**identity, "go_date": go["date"], "go_commit": go["commit"],
              "earlier_gos": [f"{g['date']}@{g['commit'][:12]}" for g in gos[:-1]],
              "changed_since_go": changed, "approved_text": f"sha256:{approval_text(then, then_allowances)}"}
    recorded = trailers(git(repo, "log", "-1", "--format=%B", go["commit"]))
    result["approval_source"] = recorded["source"]
    historical_bmad = go.get("bmad", False)
    if legacy and not historical_bmad:
        return {**result, "state": "NEEDS_NORMALIZE", "reason": "new approvals require normalized work; the legacy marker grants no exemption"}
    has_record = not historical_bmad and any(recorded.values())
    result["provenance"] = "recorded" if has_record else "not recorded"
    if has_record:
        name = epic_name(epic, lambda path: read_in(go["commit"], path))
        gaps = record_gaps(recorded, epic, go, result["approved_text"], f"{prefix}epics/{name}" if name else None)
        if gaps:
            return {**result, "state": "NO_GO_RECORD", "provenance": "incomplete",
                    "reason": f"the go commit {go['commit'][:12]} names an incomplete or inconsistent record ({'; '.join(gaps)}); it grants nothing"}
    late = None if historical_bmad or has_record else hand_go_too_late(repo, go["commit"])
    if late:
        return {**result, "state": "NO_GO_RECORD",
                "reason": f"the go commit {go['commit'][:12]} names no act of the owner and was {late}; it grants nothing: record his go with bmn plan go"}
    if go.get("withdrawn"):
        withdrawn = go["withdrawn"]
        return {**result, "state": "NO_GO_RECORD", "withdrawn_go": go["date"],
                "reason": f"the go of {go['date']} was withdrawn at {withdrawn['commit'][:12]}: the row was put {withdrawn['status']}; it grants nothing until his next go"}
    if not board.is_file():
        # No board to read now: nothing says the go still stands (96 Astra recheck).
        return {**result, "state": "NO_GO_RECORD", "reason": f"the board {board} cannot be read now; the go of {go['date']} cannot be confirmed"}
    board_now = row(board.read_text(encoding="utf-8", errors="replace"), epic)
    date_now = GO_DATE.search(board_now[1]) if board_now else None
    if date_now and date_now.group(1) != go["date"]:
        result["uncommitted_go"] = date_now.group(1)
    if board_now is None:
        return {**result, "state": "NO_GO_RECORD", "withdrawn_go": go["date"],
                "reason": f"the go of {go['date']} was withdrawn: the epic's row is no longer on the board"}
    if board_now[0] in WITHDRAWN and (committed_row is None or committed_row[0] not in WITHDRAWN):
        return {**result, "state": "NO_GO_RECORD", "withdrawn_go": go["date"],
                "reason": f"the go of {go['date']} was withdrawn: the row is now {board_now[0]}"}
    if then["Run needs"] is None and then_allowances is None:
        return {**result, **floor, "row_status": board_now[0], "state": "NO_RUN_NEEDS", "reason": "the epic had no Run needs at its go"}

    def rounds_at(commit: str) -> int:
        """What an earlier go gave: its file's number when its commit held one, its Run needs' otherwise."""
        if allowances_at(commit) is None:
            return parse_needs(sections(text_at(commit))["Run needs"])["rounds"]
        return ((read_allowances(project, epic, commit).get("at_go") or {}).get("fields") or {}).get("rounds", 0)

    held = {}
    parsed = None
    if then_allowances is not None:
        try:
            read = read_allowances(project, epic, go["commit"])
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return {**result, "state": "NO_GO_RECORD", "unconfirmed": True, "reason": f"the go's allowances file cannot be read: {exc}"}
        if read.get("state") != "recorded":
            return {**result, "state": "NO_GO_RECORD", "unconfirmed": True, "reason": f"the go's allowances file grants nothing: {read.get('reason') or read.get('state')}"}
        current = read["current"]
        parsed = current["fields"]
        held = {"allowances": {"file": read["file"], "token": read["token"], "commit": current["commit"], "source": current["source"],
                               "changes": read["changes"], "hand_edit": read.get("hand_edit"), "text": current["text"]}}
        if read.get("hand_edit"):
            result["changed_since_go"] = [*changed, "Allowances"]
    else:
        try:
            names = [p.name for p in (plan_root / "allowances").iterdir()]
        except OSError:
            names = []
        if allowance_name(epic, names):
            result["changed_since_go"] = [*changed, "Allowances"]
    return {**result, **held, "floor": True, "state": "GO", "run_needs": then["Run needs"] or "", "parsed": parsed or parse_needs(then["Run needs"]),
            "stories": STORY.findall(then_text or ""),  # the epic's stories at its go: the only story boundaries for its rounds
            # The largest allowance an earlier go gave: what a ledger that lost its count presumes used (96 Astra review).
            "earlier_rounds": max((rounds_at(g["commit"]) for g in gos[:-1]), default=0),
            "row_status": board_now[0],
            "decisions_at_go": f"git -C {repo} show {go['commit'][:12]}:<epic file>, ## Decisions"}


def run_needs(project: Path, epic: int) -> dict:
    """A working file must match the version its go/allow recorded before a run starts."""
    result = recorded_needs(project, epic)
    held = result.get("allowances")
    reason = (held or {}).get("hand_edit")
    root = result.get("plan_root")
    if root and result["state"] not in ('NEEDS_MOVE', 'PLAN_CONFLICT'):
        folder = Path(root) / "allowances"
        names = [p.name for p in folder.iterdir() if p.suffix == '.yaml' and p.stem.isdigit() and int(p.stem) == epic] if folder.is_dir() else []
        if len(names) > 1:
            reason = "duplicate working allowance files"
        elif names and not held and (result["state"] == 'GO' or result.get('floor')):
            reason = "the working allowance file was never recorded by this epic's go or allow"
    result["allowances_state"] = "in force" if held else "none"
    if reason:
        result.update(state="NOT_IN_FORCE", allowances_state="NOT IN FORCE", unconfirmed=True, floor=False,
                      reason=f"{reason}; put the file back to the last recorded version, or obtain his new go on the corrected file")
    return result


def main(argv: list[str]) -> int:
    if not argv or {"-h", "--help"} & set(argv) or not argv[0].isdigit():
        print((__doc__ or "").strip())
        return 0 if {"-h", "--help"} & set(argv) else 2
    project = Path(argv[argv.index("--project") + 1]) if "--project" in argv else Path.cwd()
    try:
        result = run_needs(project, int(argv[0]))
    except (RuntimeError, OSError, KeyError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"UNABLE: {exc}")
        return 2
    if "--json" in argv:
        print(json.dumps(result, indent=2))
        return 1 if result["state"] == "NOT_IN_FORCE" else 0
    if result["state"] == "NOT_IN_FORCE":
        print(f"ALLOWANCES: NOT IN FORCE: {result['reason']}; start no run")
        return 1
    print(f"ALLOWANCES: {result.get('allowances_state', 'none')}")
    if result["state"] == "GO":
        print(f"GO: epic {result['epic']}, go {result['go_date']}, commit {result['go_commit'][:12]} in {result['history_repo']}")
        if result["provenance"] == "recorded":
            print(f"APPROVAL: {result['approval_source']}; approved text {result['approved_text']}")
        else:
            print(f"APPROVAL: not recorded with the go (a go recorded before bmn plan go); the go stands, approved text at its commit {result['approved_text']}")
        print("RUN NEEDS (his instruction for this epic's runs, as recorded at the go):")
        print(result["run_needs"])
        held = result.get("allowances")
        if held:
            print(f"ALLOWANCES: {held['file']}, last recorded {held['commit'][:12]} ({held['source']}); token {held['token']}. The current limits, read at each boundary:")
            for name, one in result["parsed"]["limits"].items():
                ceiling = "no ceiling" if one.get("ceiling") is None else f"ceiling {one['ceiling']:g}"
                print(f"- {name}: {one['limit']:g} per {one['per']}, {ceiling}" + ("" if one.get("unit") == "count" else f", {one['unit']}"))
            for action in result["parsed"].get("may", []):
                print(f"MAY: {action}")
            for boundary in result["parsed"].get("stays_out", []):
                print(f"STAYS OUT: {boundary}")
            for one in result["parsed"].get("deferrable", []):
                print(f"DEFERRABLE: {one}")
            if held.get("hand_edit"):
                print(f"HAND_EDIT: {held['hand_edit']}")
        print(f"DECISIONS: read at the go, {result['decisions_at_go']}")
        for one in result["parsed"]["messages"]:
            print(f"MESSAGE: {' / '.join(one['people'])}; --destination {one['destination']!r}; --purpose {one['purpose']!r}")
        prepared = result["parsed"]["prepared"]
        if prepared:
            print("PREPARED (run each check yourself, as its own tool call; a failed need parks only the stories that name it):")
            for one in prepared:
                if one.get("unparsed"):
                    print(f"- unparsed, read it yourself: {one['target']}")
                elif one["none_because"]:
                    print(f"- {one['kind'] or 'nothing'}: none, because {one['none_because']}")
                else:
                    last = f"; checked {one['checked']}" if one["checked"] else ""
                    how = f"check: {one['check']}" if one["check"] else ("his step, no check" if one["kind"] == "owner step" else "no check named: say how you checked it")
                    print(f"- {one['kind']}: {one['target']}; {how}{last}")
            for problem in prepared_problems(prepared):
                print(f"PREPARED GAP, read it yourself: {problem}")
    elif result["state"] == "NEEDS_MOVE":
        print(f"NEEDS_MOVE: {result['reason']}; start no run here and report the move to the owner")
    else:
        print(f"{result['state']}: {result['reason']}; nothing is delegated beyond the invocation")
        if result.get("floor"):
            print(f"{result['state']}: the run goes on under the invocation with the default extra rounds (spend_ledger.py open prints them) and no deferrals")
        if result["state"] == "NO_GO_RECORD":
            print(f"NO_GO_RECORD: the run goes on under the invocation without {'this epic' + chr(39) + 's deferrals' if result.get('floor') else 'extra rounds or this epic' + chr(39) + 's deferrals'}; a go is "
                  "recorded only at planning (bmn plan go), never by the run, and he is never asked to restate an approval: "
                  "record any approval evidence found in the handoff as the reason the record is missing")
    if result.get("earlier_gos"):
        print(f"REAPPROVAL: earlier gos {', '.join(result['earlier_gos'])}; rounds and money they let the run use stay used")
    if result.get("changed_since_go"):
        print(f"CHANGED_SINCE_GO: {', '.join(result['changed_since_go'])}; the go's text holds, record the change under Needs your decision")
    if result.get("uncommitted_go"):
        held = "the last committed go holds" if result["state"] == "GO" else "it grants nothing until bmn plan go records it"
        print(f"UNCOMMITTED_GO: the board names go {result['uncommitted_go']}, not yet in the plan's history; {held}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
