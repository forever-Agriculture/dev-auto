#!/usr/bin/env python3
# MODULE: interruptions.py - BMN Epic 96.2/96.7: what asked the owner during named dev-auto runs, counted once per question, read-only
"""Count the questions and permission prompts BMN recorded during named dev-auto runs, read-only and bounded.

Usage: interruptions.py HANDOFF... [--db PATH] [--seconds N] [--json | --spot]

Each HANDOFF is a run's .dev-auto/handoff.md: its Run id, the lead conversations its Lead sessions and Lead host
fields name, and its time (the log's own leading stamps to the handoff's last change). Only BMN's attention
requests (state.sqlite3, opened read-only) of those conversations, or keyed with the run id, opened in that time
are read; nothing else in the home folder is scanned, and the read stops after --seconds (180), inside a query or
the classing too, with the coverage reached.

Two counts sit side by side. The old count is BMN Epic 90.1's: every request one item, classed by its words
(his by nature, push or packaging, settleable by the plan, unknown). The corrected count is one per question the
owner was asked: a `bmn ask` mirror and the terminal card a hook recorded count once when provenance establishes
it (the same conversation and the same nonempty generation, opened within 120 seconds, the mirror's question in
the card's words);
a close pair without that stays two items, labelled a possible mirror. Then each question is an owner decision
(his by nature or a push/merge/packaging act policy reserves), settleable by the plan, repeated (the same
question or key asked again in the run) or unresolved; a permission prompt is the host's, never the workflow's.
A card the agent's next question replaced in its slot keeps its opened time, so rows of one session and key at the
same instant were one card to him. With the same title that is a phantom, one call's second card; with another title
it is `replaced`, usually a re-ask, one or two calls: BMN stores no tool-call id, and the app's own record says which.
Each counts once as asked and the extra is named. BMN keeps no hook record past a restart, so extra hook runs behind
one card are not counted: `bmn hooks check` names the overlapping entries that cause them. A duplicate is one question
also asked through another route: a mirror, folded or possible.
Beside them, for BMN Epic 106: rounds and step-backs from the run's ledger, its stories done and parked from the board
the handoff names, the parked hours from the log's `<stamp> parked N.M` and `<stamp> unparked N.M` lines, usage from
the asks exported under .dev-auto/evidence, repeated requests, and how long the apps' native permission prompts held
the agent (a `bmn ask` permission card holds nothing, so it is not one; a prompt still open is named, not summed). A run
that parks more stories than it finished does not count as a success, however few cards it asked.
Output holds ids, times and classes only; --spot prints the questions' titles on screen for the lead's own
check and is never to be saved.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spend_ledger import plan_identity  # noqa: E402  the ledger's own name for a plan, so this reads the same budget

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
STAMP = re.compile(r"^(?:#+ |- )?(20\d\d-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d)?Z?)", re.M)
MIRROR_WINDOW = timedelta(seconds=120)
BUDGET = re.compile(r"\b[0-9a-f]{16}-epic-(\d+)\b")
EPIC = re.compile(r"\bepic[ -]?(\d+)\b", re.I)
BOARD = re.compile(r"(/\S+?/status\.yaml)\b")
PARKED = {"blocked", "paused"}
SLACK = timedelta(minutes=5)


class OutOfTime(Exception):
    """The count's time bound passed while a run was in one phase: read, matched, classed or counted."""

    def __init__(self, phase: str) -> None:
        super().__init__(phase)
        self.phase = phase


def past(deadline: float | None, phase: str) -> bool:
    """The one clock check every pass of a run makes (96 Astra recheck); `phase` names the pass for the coverage note."""
    return deadline is not None and time.monotonic() > deadline


def checked(items, deadline: float | None, phase: str):
    """The items, each only while the deadline has not passed."""
    for item in items:
        if past(deadline, phase):
            raise OutOfTime(phase)
        yield item
# Copied unchanged from BMN plan/references/090/baseline.py (Story 90.1) so the old count stays the old method.
HIS = re.compile(r'credential|password|secret|api[ -]?key|access token|bot token|\bsign(ed|s)?[ -]?in\b|\blog ?in\b|github account|http 404|'
                 r'private data|personal data|clarification to|change (to )?(the )?(acceptance|criteri)|acceptance criteri|amend|'
                 r'phone check|on your phone|your (short |own |live |manual )?(phone )?(check|look|test|scorecard)|after you restart|your restart|by hand|'
                 r'(replace|instead of|swap) .{0,60}(judge|reviewer|model|sonnet|opus|astra|sol|luna|haiku|fable)|'
                 r'third[- ]party|art|ann|dana|sue|another team|independent approval', re.I)
PUSH = re.compile(r'git push|push (main|master|to|the|it)|fast-forward|\bmerg|pull request|\bPRs?\b|pull/\d+|gh pr|packag|'
                  r'update:desktop|\brelease\b|deploy|gh auth switch', re.I)
PLAN = re.compile(r'design|mock|screen|layout|scope|descope|defer|remaining (epics|stories|work)|continue|which (story|epic|option)|'
                  r'pick|choose|option|repair|recheck|review|round|retry|brake|consult|spend|budget|quota|\$\d|cost|\bcap\b|'
                  r'stop gate|threshold|bigger than|hours of', re.I)


def old_class(kind: str, text: str) -> str:
    if kind == "permission":
        return "push" if PUSH.search(text) else "unknown"
    return "his" if HIS.search(text) else "push" if PUSH.search(text) else "plan" if PLAN.search(text) else "unknown"


def parse(text: str | None) -> datetime | None:
    try:
        value = datetime.fromisoformat((text or "").replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def field(text: str, name: str) -> str:
    match = re.search(rf"^- {re.escape(name)}:\s*(.*)$", text, re.M)
    return match.group(1).strip() if match else ""


def load_run(handoff: Path) -> dict:
    text = handoff.read_text(encoding="utf-8", errors="replace")
    log = handoff.with_name("log.md")
    stamps = [parse(s) for s in STAMP.findall(log.read_text(encoding="utf-8", errors="replace"))] if log.exists() else []
    end = datetime.fromtimestamp(handoff.stat().st_mtime, timezone.utc)
    stamps = [s for s in stamps if s and s <= end + SLACK]
    return {"handoff": str(handoff), "id": field(text, "Run id") or f"path:{handoff.parent.parent}",
            "conversations": sorted({c for name in ("Lead sessions", "Lead host / requested model / observed model")
                                     for c in UUID.findall(field(text, name))}),
            "start": min(stamps) - SLACK if stamps else end - timedelta(days=2), "end": end + SLACK}


def normal(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^(claude|codex|opencode) (asks|has \d+ questions):\s*", "", (text or "").strip(), flags=re.I)).casefold()


def key_stem(key: str) -> str:
    return re.sub(r"[-:](?:b|c|again|\d)$", "", key or "")


def question_texts(prompt_json: str | None, title: str) -> list[str]:
    """Each question of a card: a hook's row holds them in its prompt, every one with its own word; a `bmn ask` card is its title."""
    try:
        questions = json.loads(prompt_json or "{}").get("questions")
    except (ValueError, AttributeError):
        return [title]
    if not isinstance(questions, list) or not questions:
        return [title]
    texts = [one.get("text") for one in questions if isinstance(one, dict) and isinstance(one.get("text"), str)]
    return texts if len(texts) == len(questions) else [title]


def read_items(connection: sqlite3.Connection, run: dict, deadline: float | None = None) -> list[dict]:
    rows = connection.execute(
        "SELECT request_id, session_id, request_key, kind, opened_at, opened_by, title, substr(coalesce(body, ''), 1, 2000), "
        "substr(coalesce(prompt_json, ''), 1, 300), producer_json, resolved_at, CASE WHEN kind = 'question' THEN prompt_json END FROM attention_request "
        "WHERE kind IN ('question', 'permission') AND opened_at >= ? AND opened_at <= ? ORDER BY opened_at, request_id",
        (run["start"].isoformat().replace("+00:00", "Z"), run["end"].isoformat().replace("+00:00", "Z"))).fetchall()
    items = []
    for request_id, session, key, kind, opened, opened_by, title, body, prompt, producer, resolved, whole in checked(rows, deadline, "read"):
        try:
            origin = json.loads(producer) if producer else {}
        except ValueError:
            origin = {}
        conversation = origin.get("conversationReference") or ""
        # The run's own: a lead conversation or BMN session its handoff names, or a key carrying its run id.
        if conversation not in run["conversations"] and session not in run["conversations"] and run["id"].lower() not in (key or "").lower():
            continue
        items.append({"request": request_id, "session": session, "opened": opened, "resolved": resolved, "kind": kind, "via": opened_by or "", "key": key or "",
                      "conversation": conversation, "generation": origin.get("generation") or "",
                      "_title": title or "", "_questions": question_texts(whole, title or ""), "_text": " ".join(filter(None, [title, body, prompt if kind == "permission" else ""]))})
    return items


def correct(items: list[dict], deadline: float | None = None) -> list[dict]:
    """One entry per question asked: mirrors folded into their card when provenance shows it, then classed."""
    cards = [i for i in checked(items, deadline, "matched") if i["kind"] == "question" and i["via"].startswith("hook:")]
    for item in checked(items, deadline, "matched"):
        item["mirror_of"] = item["possible_mirror_of"] = None
        if item["kind"] != "question" or item["via"].startswith("hook:"):
            continue
        opened = parse(item["opened"])
        near = [c for c in checked(cards, deadline, "matched") if c["conversation"] == item["conversation"] and item["conversation"] and opened
                and (card := parse(c["opened"])) and abs(card - opened) <= MIRROR_WINDOW]
        # Equal empty generations are no provenance: such a pair stays two, a possible mirror (96 Astra review).
        same = [c for c in checked(near, deadline, "matched") if item["generation"] and c["generation"] == item["generation"]
                and normal(item["_title"]) and normal(item["_title"]) in normal(c["_text"])]
        if same:
            item["mirror_of"] = same[0]["request"]
        elif near:
            item["possible_mirror_of"] = near[0]["request"]
    asked: dict[str, str] = {}
    stems: dict[str, str] = {}
    slots: dict[tuple[str, str, str], dict[str, str]] = {}
    for item in checked(items, deadline, "classed"):
        if item["mirror_of"]:
            item["class"] = "mirror"
            continue
        if item["kind"] == "permission":
            item["class"] = "native-permission"
            continue
        slot = slots.setdefault((item["session"], item["key"], item["opened"]), {}) if item["via"].startswith("hook:") else {}
        if slot:
            item["class"], item["same_card_as"] = ("phantom" if normal(item["_title"]) in slot else "replaced"), next(iter(slot.values()))
            continue
        slot[normal(item["_title"])] = item["request"]
        title, stem = normal(item["_title"]), key_stem(item["key"])
        earlier = asked.get(title) or (stems.get(stem) if item["via"] == "cli" and stem else None)
        asked.setdefault(title, item["request"])
        if item["via"] == "cli" and stem:
            stems.setdefault(stem, item["request"])
        if earlier:
            item["class"], item["repeats"] = "repeated", earlier
            continue
        words = old_class("question", item["_text"])
        item["class"] = "owner-decision" if words in ("his", "push") else "plan-settleable" if words == "plan" else "unresolved"
    return items


LONG_PROMPT = timedelta(minutes=30)


def native_prompts(items: list[dict], deadline: float | None) -> dict:
    """The apps' own permission prompts, which hold the agent until answered; a card from `bmn ask` does not.

    At most: a prompt's row closes when the command has finished (PostToolUse, bmn-hooks.mjs), and no app reports the moment he
    answered, so a slow command after a quick yes counts in full. A row over 30 minutes needs its transcript to say which.
    """
    count = over = still_open = 0
    held = timedelta()
    for item in checked(items, deadline, "counted"):
        if item["kind"] != "permission" or not re.match(r"hook:[^:]+:PermissionRequest$", item["via"]):
            continue
        count += 1
        opened, resolved = parse(item["opened"]), parse(item["resolved"])
        if opened is None or resolved is None:
            still_open += 1
            continue
        held += resolved - opened
        over += resolved - opened > LONG_PROMPT
    return {"count": count, "over_30_minutes_at_most": over, "hours_held_at_most": round(held.total_seconds() / 3600, 1), "open": still_open}


def run_files(run: dict) -> tuple[str, str]:
    handoff = Path(run["handoff"])
    log = handoff.with_name("log.md")
    return handoff.read_text(encoding="utf-8", errors="replace"), log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""


def rounds_taken(budget: str | None) -> dict:
    """Rounds and step-backs from the run's ledger, read and never locked; no ledger says so."""
    found = {"used": 0, "step_backs": 0, "readable": False}
    if not budget:
        return found
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    try:
        rounds = json.loads((base / "dev-auto" / "budgets" / f"{budget}.json").read_text(encoding="utf-8")).get("rounds", {})
    except (OSError, ValueError):
        return found
    taken = [use for use in rounds.values() if isinstance(use, dict) and use.get("answer") == "TAKEN"]
    return {"used": len(taken), "step_backs": sum(1 for use in taken if use.get("step_back")), "readable": True}


def parked_hours(log: str, stories: list[str], end: datetime) -> tuple[float, list[str]]:
    """From each `<stamp> parked N.M` to its `unparked`, or the run's end for a story still parked; also the parked stories with no such line."""
    held = timedelta()
    since: dict[str, datetime] = {}
    seen: set[str] = set()
    for line in log.splitlines():
        stamp = STAMP.match(line)
        at = parse(stamp.group(1)) if stamp else None
        match = re.search(r"\b(un)?parked (\d+\.\d+)\b", line)
        if at is None or match is None:
            continue
        seen.add(match.group(2))
        if match.group(1):
            if match.group(2) in since:
                held += at - since.pop(match.group(2))
        else:
            since.setdefault(match.group(2), at)
    for story, at in since.items():
        if story in stories:
            held += end - at
    return round(held.total_seconds() / 3600, 1), [story for story in stories if story not in seen]


def plan_of(checkout: Path) -> dict:
    """What `bmn plan status` says of this checkout: its board and plan root, when the handoff does not name them; {} when it cannot say."""
    try:
        done = subprocess.run(["bmn", "plan", "status", "--json", "--project", str(checkout)], capture_output=True, text=True, timeout=15)
        return json.loads(done.stdout) if done.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def stories_of(run: dict, board: str | None, log: str, epic: str | None) -> dict:
    """The epic's rows on the run's board: done and parked, and whether the run counts as a success."""
    found = {"done": 0, "parked": [], "parked_hours": 0.0, "parked_without_a_line": [], "other": 0, "readable": False, "counts_as_success": False}
    if not epic or not board:
        return found
    try:
        rows = re.findall(rf"^\s*{epic}-(\d+)-[\w-]+:\s*([\w-]+)", Path(board).read_text(encoding="utf-8"), re.M)
    except OSError:
        return found
    live = [(f"{epic}.{number}", state) for number, state in rows if state != "dropped"]
    parked = [story for story, state in live if state in PARKED]
    done = sum(1 for _, state in live if state == "done")
    hours, unstamped = parked_hours(log, parked, run["end"])
    return {"done": done, "parked": parked, "parked_hours": hours, "parked_without_a_line": unstamped, "other": len(live) - done - len(parked),
            "readable": bool(live), "counts_as_success": bool(live) and len(parked) <= done}


def ask_usage(run: dict) -> dict:
    """The asks exported under the run's evidence, by BMN's own totals; the lead's sessions are named for `check.py usage`."""
    found = {"asks": 0, "input_tokens": 0, "output_tokens": 0, "lead_sessions": len(run["conversations"])}
    evidence = Path(run["handoff"]).with_name("evidence")
    for outcome in sorted(evidence.rglob("outcome.json")) if evidence.is_dir() else []:
        try:
            usage = json.loads(outcome.read_text(encoding="utf-8")).get("usage")
        except (OSError, ValueError):
            continue
        found["asks"] += 1
        if isinstance(usage, dict):
            for name in ("input_tokens", "output_tokens"):
                found[name] += usage.get(name) if isinstance(usage.get(name), int) else 0
    return found


def outcomes(run: dict) -> dict:
    handoff, log = run_files(run)
    named = BUDGET.search(handoff) or BUDGET.search(log)
    board = BOARD.search(handoff)
    plan = {} if named and board else plan_of(Path(run["handoff"]).parent.parent)
    selected = EPIC.search(field(handoff, "Project / selected epics")) or EPIC.search(field(handoff, "Run id"))
    epic = named.group(1) if named else selected.group(1) if selected else None
    budget = named.group(0) if named else None
    if budget is None and epic and plan.get("plan_root"):
        budget = f"{hashlib.sha256(plan_identity(plan['plan_root']).encode()).hexdigest()[:16]}-epic-{epic}"
    return {"rounds": rounds_taken(budget), "stories": stories_of(run, board.group(1) if board else plan.get("board"), log, epic), "usage": ask_usage(run)}


CLASSES = ("owner-decision", "plan-settleable", "repeated", "unresolved", "native-permission", "phantom", "replaced")


def summary(run: dict, items: list[dict], deadline: float | None) -> dict:
    """The run's two counts and its items, in one pass that keeps the deadline."""
    old: dict[str, int] = {}
    corrected = {name: 0 for name in CLASSES}
    mirrors = possible = 0
    projected = []
    for item in checked(items, deadline, "counted"):
        words = old_class(item["kind"], item["_text"])
        old[words] = old.get(words, 0) + 1
        corrected[item["class"]] = corrected.get(item["class"], 0) + 1
        mirrors += item["class"] == "mirror"
        possible += bool(item["possible_mirror_of"])
        projected.append({"request": item["request"][:8], "opened": item["opened"][:16], "kind": item["kind"], "class": item["class"],
                          **({"mirror_of": item["mirror_of"][:8]} if item["mirror_of"] else {}),
                          **({"possible_mirror_of": item["possible_mirror_of"][:8]} if item["possible_mirror_of"] else {}),
                          **({"repeats": item["repeats"][:8]} if item.get("repeats") else {}),
                          **({"same_card_as": item["same_card_as"][:8]} if item.get("same_card_as") else {})})
    return {
        "run": run["id"], "handoff": run["handoff"], "conversations": len(run["conversations"]),
        "from": run["start"].isoformat(timespec="minutes"), "to": run["end"].isoformat(timespec="minutes"),
        "old_count": {"total": len(items), **{k: old.get(k, 0) for k in ("his", "push", "plan", "unknown")}},
        "corrected_count": {"questions_asked": sum(corrected[c] for c in CLASSES[:4]), **{c: corrected[c] for c in CLASSES},
                            "mirrors_folded": mirrors, "possible_mirrors_kept": possible},
        "items": projected, "_items": items}


def count(handoffs: list[Path], db: Path, seconds: float) -> dict:
    deadline = time.monotonic() + seconds
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    # The bound holds inside a query too: SQLite abandons it once the deadline passes.
    connection.set_progress_handler(lambda: int(past(deadline, "read")), 1000)
    out = {"db": str(db), "bound_seconds": seconds, "complete": True, "runs": []}
    try:
        runs(handoffs, connection, deadline, out)
    finally:
        connection.close()
    return out


def runs(handoffs: list[Path], connection: sqlite3.Connection, deadline: float, out: dict) -> None:
    for handoff in handoffs:
        if past(deadline, "read"):
            out["complete"] = False
            out["runs"].append({"handoff": str(handoff), "skipped": "the time bound was reached first"})
            continue
        run = load_run(handoff)
        try:
            entry = summary(run, correct(read_items(connection, run, deadline), deadline), deadline)
            entry["native_prompts"] = native_prompts(entry["_items"], deadline)
            entry.update(outcomes(run))
            if past(deadline, "counted"):
                raise OutOfTime("counted")
        except (OutOfTime, sqlite3.OperationalError) as exc:
            if isinstance(exc, sqlite3.OperationalError) and not past(deadline, "read"):
                raise
            out["complete"] = False
            out["runs"].append({"handoff": str(handoff), "skipped": f"the time bound was reached while it was {exc.phase if isinstance(exc, OutOfTime) else 'read'}"})
            continue
        out["runs"].append(entry)


def main(argv: list[str]) -> int:
    if not argv or {"-h", "--help"} & set(argv):
        print((__doc__ or "").strip())
        return 0 if argv else 2
    values = {name: argv[argv.index(name) + 1] for name in ("--db", "--seconds") if name in argv and argv.index(name) + 1 < len(argv)}
    handoffs = [Path(a) for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in ("--db", "--seconds"))]
    db = Path(values.get("--db") or Path.home() / ".local" / "share" / "ai-terminal" / "state.sqlite3")
    try:
        result = count(handoffs, db, float(values.get("--seconds", 180)))
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"UNABLE: {exc}")
        return 2
    if "--spot" in argv:
        for run in result["runs"]:
            for item in run.get("_items", []):
                print(run["run"][-24:], item["request"][:8], item["opened"][5:16], item["class"], "|", item["_title"][:110])
        return 0
    for run in result["runs"]:
        run.pop("_items", None)
    if "--json" in argv:
        print(json.dumps(result, indent=1))
        return 0
    for run in result["runs"]:
        if "skipped" in run:
            print(f"SKIPPED: {run['handoff']}: {run['skipped']}")
            continue
        old, new = run["old_count"], run["corrected_count"]
        print(f"{run['run']}: old count {old['total']} (his {old['his']}, push {old['push']}, plan {old['plan']}, unknown {old['unknown']}); "
              f"corrected: {new['questions_asked']} questions asked (owner decisions {new['owner-decision']}, plan-settleable "
              f"{new['plan-settleable']}, repeated {new['repeated']}, unresolved {new['unresolved']}), {new['native-permission']} "
              f"permission prompts, {new['mirrors_folded']} mirrors folded, {new['possible_mirrors_kept']} possible mirrors kept apart")
        prompts, rounds, stories, usage = run["native_prompts"], run["rounds"], run["stories"], run["usage"]
        still = f", {prompts['open']} still open" if prompts["open"] else ""
        print(f"  phantoms {new['phantom']}, replaced {new['replaced']}, duplicates {new['mirrors_folded'] + new['possible_mirrors_kept']}, repeated requests {new['repeated']}; "
              f"rounds {rounds['used'] if rounds['readable'] else 'no ledger'}, step-backs {rounds['step_backs'] if rounds['readable'] else 'no ledger'}; "
              f"native waits {prompts['count']}, at most {prompts['over_30_minutes_at_most']} over 30 minutes, at most "
              f"{prompts['hours_held_at_most']} hours held, to the command's end{still}")
        unstamped = f", {len(stories['parked_without_a_line'])} with no parked line" if stories["parked_without_a_line"] else ""
        finished = (f"stories done {stories['done']}, parked {len(stories['parked'])} ({stories['parked_hours']} hours{unstamped}), others {stories['other']}"
                    f"{'' if stories['counts_as_success'] else '; not a success: it parked more than it finished'}") if stories["readable"] else "stories: no board"
        print(f"  {finished}; usage {usage['asks']} asks, {usage['input_tokens']} in, {usage['output_tokens']} out, {usage['lead_sessions']} lead sessions")
    print("COVERAGE: complete" if result["complete"] else "COVERAGE: partial, the time bound was reached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
