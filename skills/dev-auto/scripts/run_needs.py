#!/usr/bin/env python3
# MODULE: run_needs.py - BMN Epic 90.3: the owner's go on an epic and the Run needs it approved, read from the plan's history
"""Name an epic's go and the Run needs and Decisions it approved, read-only.

Usage: run_needs.py EPIC [--project P] [--json]

The go is the approval event, not a later snapshot: the commit of the board in which the epic's row
changed to `ready` with `go YYYY-MM-DD` in its note, from a parent where the row had another status or
another go date. A go date first committed while the row is already past `ready` (the `ready` snapshot was
never committed) grants nothing. A BMAD board's go is the commit in which the row's dated `go` comment
appeared or changed. Later commits keeping the row keep the go; a new go date or a return to `ready` is a
reapproval, a new go, and what earlier gos let the run use stays used. A go recorded with `bmn plan go`
(BMN Epic 96.1) names in its commit message the owner's act (Approval-Source) and the SHA-256 of the Run
needs and Decisions he approved (Approved-Text); one whose text at the commit differs from that hash grants
nothing, and an older go without them stands with its source unrecorded. A row put back to `backlog` or
`dropped` after the go withdraws it.

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
STORY = re.compile(r"^#{2,4} Story (\d+\.\d+)\b", re.M)
SECTIONS = ("Run needs", "Decisions")


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


def find_gos(repo: Path, board: str, epic: int, bmad: bool) -> list[dict]:
    """Every go of the epic in the board's history, oldest first."""
    commits = git(repo, "log", "--reverse", "--format=%H", "--", board).split()
    gos, previous, last_date = [], None, None
    for commit in commits:
        try:
            current = row(git(repo, "show", f"{commit}:{board}"), epic)
        except RuntimeError:
            current = None  # the board was removed in this commit
        if current:
            status, note = current
            match = GO_DATE.search(note)
            date = match.group(1) if match else None
            if bmad:
                new = date is not None and date != last_date
            else:
                # Only the move to ready with a dated go approves (90.3 AC1); a date first seen in a later status delegates nothing.
                new = status == "ready" and date is not None and (previous is None or previous[0] != "ready" or previous[1] != date)
            if new:
                gos.append({"date": date, "commit": commit})
                last_date = date
            previous = (status, date)
        else:
            previous = None
    return gos


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


def trailers(message: str) -> dict[str, str | None]:
    """The owner's act and the approved text a `bmn plan go` commit names (96.1); None for an older go."""
    def field(name: str) -> str | None:
        match = re.search(rf"^{name}: (.+)$", message, re.M)
        return match.group(1).strip() if match else None
    return {"source": field("Approval-Source"), "approved": field("Approved-Text")}


def epic_text_bmn(epic: int, read) -> str | None:
    names = [name for name in read("epics") if re.fullmatch(rf"0*{epic}-[\w.-]+\.md", name)]
    return read(f"epics/{names[0]}") if len(names) == 1 else None


def epic_text_bmad(text: str | None, epic: int) -> str | None:
    match = re.search(rf"^(#{{1,3}}) Epic {epic}\b[^\n]*\n(.*?)(?=^\1 Epic \d|\Z)", text or "", re.M | re.S)
    return match.group(0) if match else None


def parse_needs(text: str | None) -> dict:
    needs = {"rounds": 0, "deferrable": [], "money_cap": None, "named_actions": None}
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
    return needs


def run_needs(project: Path, epic: int) -> dict:
    status = resolve(project)
    board = Path(status["board"])
    bmad = status.get("format") == "bmad"
    repo = Path(status.get("board_checkout") or status["product_root"])
    plan_root = Path(status.get("plan_root") or repo)
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
        gos = find_gos(repo, board_rel, epic, bmad)
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

    def read_at(path: str):
        if path == "epics":
            return git(repo, "ls-tree", "--name-only", f"{go['commit']}:{prefix}epics").split()
        return git(repo, "show", f"{go['commit']}:{prefix}{path}")

    if bmad:
        then_text = None
        for path in git(repo, "ls-tree", "-r", "--name-only", go["commit"]).split():
            if path.endswith(".md") and "planning-artifacts" in path:
                then_text = epic_text_bmad(git(repo, "show", f"{go['commit']}:{path}"), epic) or then_text
    else:
        try:
            then_text = epic_text_bmn(epic, read_at)
        except RuntimeError:
            then_text = None
    then = sections(then_text)
    changed = [name for name in SECTIONS if (then[name] or "") != (now[name] or "")]
    result = {**identity, "go_date": go["date"], "go_commit": go["commit"],
              "earlier_gos": [f"{g['date']}@{g['commit'][:12]}" for g in gos[:-1]],
              "changed_since_go": changed, "approved_text": f"sha256:{approval_text(then)}"}
    try:
        recorded = trailers(git(repo, "log", "-1", "--format=%B", go["commit"]))
    except RuntimeError:
        recorded = {"source": None, "approved": None}
    result["approval_source"] = recorded["source"]
    result["provenance"] = "recorded" if recorded["approved"] else "not recorded"
    if recorded["approved"] and recorded["approved"] != result["approved_text"]:
        return {**result, "state": "NO_GO_RECORD",
                "reason": f"the go commit {go['commit'][:12]} names approved text {recorded['approved'][:19]}…, not the Run needs and Decisions it holds; it grants nothing"}
    board_now = row(board.read_text(encoding="utf-8", errors="replace"), epic) if board.exists() else None
    date_now = GO_DATE.search(board_now[1]) if board_now else None
    if date_now and date_now.group(1) != go["date"]:
        result["uncommitted_go"] = date_now.group(1)
    if board_now and board_now[0] in ("backlog", "dropped"):
        return {**result, "state": "NO_GO_RECORD", "withdrawn_go": go["date"],
                "reason": f"the go of {go['date']} was withdrawn: the row is now {board_now[0]}"}
    if then["Run needs"] is None:
        return {**result, "state": "NO_RUN_NEEDS", "reason": "the epic had no Run needs at its go"}
    return {**result, "state": "GO", "run_needs": then["Run needs"], "parsed": parse_needs(then["Run needs"]),
            "stories": STORY.findall(then_text or ""),  # the epic's stories at its go: the only story boundaries for its rounds
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
