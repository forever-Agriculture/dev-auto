#!/usr/bin/env python3
# MODULE: run_needs.py - BMN Epic 90.3: the owner's go on an epic and the Run needs it approved, read from the plan's history
"""Name an epic's go and the Run needs and Decisions it approved, read-only.

Usage: run_needs.py EPIC [--project P] [--json]

The go is the approval event, not a later snapshot: the commit of the board in which the epic's row
changed to `ready` with `go YYYY-MM-DD` in its note, from a parent where the row had another status or
another go date, or a commit `bmn plan go` wrote for the epic (its Go-Epic trailer), however little the row
changed: a second go on the same day with new terms is a new go. A go date first committed while the row is
already past `ready` (the `ready` snapshot was never committed) grants nothing. A BMAD board's go is the commit in which the row's dated `go` comment
appeared or changed. Later commits keeping the row keep the go; a new go date or a return to `ready` is a
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

Prints one of GO, NO_GO_RECORD or NO_RUN_NEEDS, then CHANGED_SINCE_GO when Run needs or Decisions differ
today from the go's commit (the run keeps the go's text and records the change for the owner). Exit 0;
2 only when the plan cannot be resolved (UNABLE).
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
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
PREPARED_KINDS = "account|credential|service|command|message|owner step"
PREPARED_NEED = re.compile(rf"^((?:{PREPARED_KINDS})(?:\s*,\s*(?:{PREPARED_KINDS}))*)\s*:\s*(.*)$", re.I | re.S)
NONE_BECAUSE = re.compile(r"^none\s*,?\s*because\s+(.+)$", re.I | re.S)
CHECKED_ON = re.compile(r"\bchecked\s+(\d{4}-\d{2}-\d{2})")


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60)
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


def find_gos(repo: Path, board: str, epic: int, bmad: bool) -> tuple[list[dict], tuple[str, str] | None]:
    """Every go of the epic in the board's history, oldest first, each with the withdrawal that followed it; and the row at the last commit."""
    commits = git(repo, "log", "--reverse", "--format=%H", "--", board).split()
    # A commit bmn plan go wrote names the epic in its message; it is a go even when the row's line did not change (96 Astra review).
    recorded = set() if bmad else set(git(repo, "log", "--format=%H", "-E", f"--grep=^Go-Epic: 0*{epic}[[:space:]]*$").split())
    if recorded - set(commits):
        wanted = set(commits) | recorded
        commits = [commit for commit in git(repo, "rev-list", "--reverse", "--topo-order", "HEAD").split() if commit in wanted]
    gos, previous, last_date = [], None, None
    for commit in commits:
        try:
            current = row(git(repo, "show", f"{commit}:{board}"), epic)
        except RuntimeError:
            current = None  # the board was removed in this commit
        status, note = current or (None, "")
        match = GO_DATE.search(note)
        date = match.group(1) if match else None
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


def sections(text: str | None) -> dict[str, str | None]:
    """The `## Run needs` and `## Decisions` sections (or `### ` ones in a BMAD epics file), their text without the heading."""
    out = {}
    for name in SECTIONS:
        match = re.search(rf"^(#{{2,4}}) {re.escape(name)}[ \t]*\n(.*?)(?=^#{{1,4}} |\Z)", text or "", re.M | re.S)
        out[name] = match.group(2).strip(" \t\r\n") if match else None
    return out


def approval_text(found: dict[str, str | None]) -> str:
    """The SHA-256 a go names for its Run needs and Decisions; `bmn plan go` and `bmn plan status` hash them the same way."""
    text = f"Run needs\n{found['Run needs'] or ''}\nDecisions\n{found['Decisions'] or ''}\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def parse_needs(text: str | None) -> dict:
    needs = {"rounds": 0, "deferrable": [], "money_cap": None, "named_actions": None, "prepared": []}
    for line in (text or "").splitlines():
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
        elif "named action" in name:
            needs["named_actions"] = None if value.lower().startswith("none") else value
        elif "prepared" in name:
            needs["prepared"] = parse_prepared(value)
    return needs


def run_needs(project: Path, epic: int) -> dict:
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
    board_rel = board.relative_to(repo).as_posix()

    def current_read(path: str):
        target = plan_root / path
        return sorted(p.name for p in target.iterdir()) if target.is_dir() else target.read_text(encoding="utf-8", errors="replace")

    def epic_now() -> str | None:
        if not bmad:
            try:
                return epic_text_bmn(epic, current_read)
            except OSError:
                return None
        for path in sorted((board.parent.parent / "planning-artifacts").rglob("*.md")):
            text = epic_text_bmad(path.read_text(encoding="utf-8", errors="replace"), epic)
            if text:
                return text
        return None

    now = sections(epic_now())
    try:
        gos, committed_row = find_gos(repo, board_rel, epic, bmad)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        if now["Run needs"] is None:
            return {**identity, "state": "NO_RUN_NEEDS", "reason": "the epic has no Run needs"}
        return {**identity, "state": "NO_GO_RECORD", "reason": f"the board's history cannot be read: {exc}"}
    if not gos:
        if now["Run needs"] is None:
            return {**identity, "state": "NO_RUN_NEEDS", "reason": "the epic has no Run needs"}
        result = {**identity, "state": "NO_GO_RECORD", "reason": "no commit records a go for this epic"}
        board_now = row(board.read_text(encoding="utf-8", errors="replace"), epic) if board.exists() else None
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
        if bmad:
            found = None
            for path in git(repo, "ls-tree", "-r", "--name-only", commit).split():
                if path.endswith(".md") and "planning-artifacts" in path:
                    found = epic_text_bmad(git(repo, "show", f"{commit}:{path}"), epic) or found
            return found
        try:
            return epic_text_bmn(epic, lambda path: read_in(commit, path))
        except RuntimeError:
            return None

    then_text = text_at(go["commit"])
    then = sections(then_text)
    changed = [name for name in SECTIONS if (then[name] or "") != (now[name] or "")]
    result = {**identity, "go_date": go["date"], "go_commit": go["commit"],
              "earlier_gos": [f"{g['date']}@{g['commit'][:12]}" for g in gos[:-1]],
              "changed_since_go": changed, "approved_text": f"sha256:{approval_text(then)}"}
    recorded = trailers(git(repo, "log", "-1", "--format=%B", go["commit"]))
    result["approval_source"] = recorded["source"]
    has_record = not bmad and any(recorded.values())
    result["provenance"] = "recorded" if has_record else "not recorded"
    if has_record:
        name = epic_name(epic, lambda path: read_in(go["commit"], path))
        gaps = record_gaps(recorded, epic, go, result["approved_text"], f"{prefix}epics/{name}" if name else None)
        if gaps:
            return {**result, "state": "NO_GO_RECORD", "provenance": "incomplete",
                    "reason": f"the go commit {go['commit'][:12]} names an incomplete or inconsistent record ({'; '.join(gaps)}); it grants nothing"}
    late = None if bmad or has_record else hand_go_too_late(repo, go["commit"])
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
    if then["Run needs"] is None:
        return {**result, "state": "NO_RUN_NEEDS", "reason": "the epic had no Run needs at its go"}
    return {**result, "state": "GO", "run_needs": then["Run needs"], "parsed": parse_needs(then["Run needs"]),
            "stories": STORY.findall(then_text or ""),  # the epic's stories at its go: the only story boundaries for its rounds
            # The largest allowance an earlier go gave: what a ledger that lost its count presumes used (96 Astra review).
            "earlier_rounds": max((parse_needs(sections(text_at(g["commit"]))["Run needs"])["rounds"] for g in gos[:-1]), default=0),
            "row_status": board_now[0],
            "decisions_at_go": f"git -C {repo} show {go['commit'][:12]}:<epic file>, ## Decisions"}


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
        return 0
    if result["state"] == "GO":
        print(f"GO: epic {result['epic']}, go {result['go_date']}, commit {result['go_commit'][:12]} in {result['history_repo']}")
        if result["provenance"] == "recorded":
            print(f"APPROVAL: {result['approval_source']}; approved text {result['approved_text']}")
        else:
            print(f"APPROVAL: not recorded with the go (a go recorded before bmn plan go); the go stands, approved text at its commit {result['approved_text']}")
        print("RUN NEEDS (his instruction for this epic's runs, as recorded at the go):")
        print(result["run_needs"])
        print(f"DECISIONS: read at the go, {result['decisions_at_go']}")
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
    else:
        print(f"{result['state']}: {result['reason']}; nothing is delegated beyond the invocation")
        if result["state"] == "NO_GO_RECORD":
            print("NO_GO_RECORD: the run goes on under the invocation without this epic's extra rounds or deferrals; a go is "
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
