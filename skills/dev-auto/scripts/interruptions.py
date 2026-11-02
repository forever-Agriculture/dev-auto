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
Beside them, for BMN Epic 103: questions by the reason word they start with (`none` for a bare one, a mirror once),
the question cards BMN handed back and the repeats that then reached him (its count, which holds no question's text),
and how long the apps' native permission prompts held the agent (a `bmn ask` permission card holds nothing, so it is
not one; a prompt still open is named, not summed).
Output holds ids, times and classes only; --spot prints the questions' titles on screen for the lead's own
check and is never to be saved.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
STAMP = re.compile(r"^(?:#+ |- )?(20\d\d-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d)?Z?)", re.M)
MIRROR_WINDOW = timedelta(seconds=120)
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
        items.append({"request": request_id, "opened": opened, "resolved": resolved, "kind": kind, "via": opened_by or "", "key": key or "",
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
    for item in checked(items, deadline, "classed"):
        if item["mirror_of"]:
            item["class"] = "mirror"
            continue
        if item["kind"] == "permission":
            item["class"] = "native-permission"
            continue
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


REASON_WORDS = ("Go", "Money", "Scope", "Privacy", "Interface", "Irreversible", "Access", "Taste", "Asked")
HAND_BACKS_KEY = "question-hand-backs-v1"
LONG_PROMPT = timedelta(minutes=30)


def reason_word(title: str) -> str:
    """The word a question's title starts with after its app's prefix, as BMN's list spells it (D6), or `none`."""
    match = re.match(r"([a-z]+):\s*\S", normal(title))
    return next((word for word in REASON_WORDS if match and word.lower() == match.group(1)), "none")


def reasons(items: list[dict], deadline: float | None) -> dict[str, int]:
    found: dict[str, int] = {}
    for item in checked(items, deadline, "counted"):
        if item["kind"] == "question" and item["class"] != "mirror":
            for text in item["_questions"]:
                word = reason_word(text)
                found[word] = found.get(word, 0) + 1
    return found


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


def hand_backs(connection: sqlite3.Connection, run: dict) -> dict:
    """BMN's count of question cards handed back and repeated in this run's conversations and time; an older BMN has none."""
    found = {"handed_back": 0, "repeated": 0, "readable": False, "may_have_lost": 0}
    try:
        row = connection.execute("SELECT value_json FROM app_setting WHERE key = ?", (HAND_BACKS_KEY,)).fetchone()
        kept = json.loads(row[0]) if row else None
        entries, dropped = (kept["entries"], kept.get("dropped", 0)) if kept else (None, 0)
    except (sqlite3.OperationalError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, sqlite3.OperationalError) and "no such" not in str(exc):
            raise
        return found
    if not isinstance(entries, list):
        return found
    found["readable"] = True
    # BMN keeps the newest entries: older ones that fell off can belong to this run only if what is kept starts after it began.
    times = [at for at in (parse(entry.get("at")) if isinstance(entry, dict) else None for entry in entries) if at is not None]
    if isinstance(dropped, int) and dropped > 0 and (not times or min(times) > run["start"]):
        found["may_have_lost"] = dropped
    for entry in entries:
        at = parse(entry.get("at")) if isinstance(entry, dict) else None
        if at is None or not run["start"] <= at <= run["end"]:
            continue
        if entry.get("conversation") in run["conversations"] or entry.get("sessionId") in run["conversations"]:
            found["handed_back" if entry.get("outcome") == "handed-back" else "repeated"] += 1
    return found


CLASSES = ("owner-decision", "plan-settleable", "repeated", "unresolved", "native-permission")


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
                          **({"repeats": item["repeats"][:8]} if item.get("repeats") else {})})
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
            entry["reasons"] = reasons(entry["_items"], deadline)
            entry["native_prompts"] = native_prompts(entry["_items"], deadline)
            entry["hand_backs"] = hand_backs(connection, run)
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
        words = ", ".join(f"{word} {count}" for word, count in sorted(run["reasons"].items(), key=lambda pair: (-pair[1], pair[0]))) or "none asked"
        back, prompts = run["hand_backs"], run["native_prompts"]
        kept = "" if back["readable"] else " (no count in this database)"
        if back["may_have_lost"]:
            kept = f" (at least; {back['may_have_lost']} older entries are no longer kept)"
        still = f", {prompts['open']} still open" if prompts["open"] else ""
        print(f"  reasons: {words}; handed back {back['handed_back']}, repeated {back['repeated']}{kept}; "
              f"native prompts {prompts['count']}, at most {prompts['over_30_minutes_at_most']} over 30 minutes, at most "
              f"{prompts['hours_held_at_most']} hours held, to the command's end{still}")
    print("COVERAGE: complete" if result["complete"] else "COVERAGE: partial, the time bound was reached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
