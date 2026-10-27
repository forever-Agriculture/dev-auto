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
    """The count's time bound passed while a run was being read or classed."""
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


def read_items(connection: sqlite3.Connection, run: dict) -> list[dict]:
    rows = connection.execute(
        "SELECT request_id, session_id, request_key, kind, opened_at, opened_by, title, substr(coalesce(body, ''), 1, 2000), "
        "substr(coalesce(prompt_json, ''), 1, 300), producer_json FROM attention_request "
        "WHERE kind IN ('question', 'permission') AND opened_at >= ? AND opened_at <= ? ORDER BY opened_at, request_id",
        (run["start"].isoformat().replace("+00:00", "Z"), run["end"].isoformat().replace("+00:00", "Z"))).fetchall()
    items = []
    for request_id, session, key, kind, opened, opened_by, title, body, prompt, producer in rows:
        try:
            origin = json.loads(producer) if producer else {}
        except ValueError:
            origin = {}
        conversation = origin.get("conversationReference") or ""
        # The run's own: a lead conversation or BMN session its handoff names, or a key carrying its run id.
        if conversation not in run["conversations"] and session not in run["conversations"] and run["id"].lower() not in (key or "").lower():
            continue
        items.append({"request": request_id, "opened": opened, "kind": kind, "via": opened_by or "", "key": key or "",
                      "conversation": conversation, "generation": origin.get("generation") or "",
                      "_title": title or "", "_text": " ".join(filter(None, [title, body, prompt if kind == "permission" else ""]))})
    return items


def correct(items: list[dict], deadline: float | None = None) -> list[dict]:
    """One entry per question asked: mirrors folded into their card when provenance shows it, then classed."""
    cards = [i for i in items if i["kind"] == "question" and i["via"].startswith("hook:")]
    for item in items:
        if deadline is not None and time.monotonic() > deadline:
            raise OutOfTime
        item["mirror_of"] = item["possible_mirror_of"] = None
        if item["kind"] != "question" or item["via"].startswith("hook:"):
            continue
        opened = parse(item["opened"])
        near = [c for c in cards if c["conversation"] == item["conversation"] and item["conversation"] and opened
                and (card := parse(c["opened"])) and abs(card - opened) <= MIRROR_WINDOW]
        # Equal empty generations are no provenance: such a pair stays two, a possible mirror (96 Astra review).
        same = [c for c in near if item["generation"] and c["generation"] == item["generation"]
                and normal(item["_title"]) and normal(item["_title"]) in normal(c["_text"])]
        if same:
            item["mirror_of"] = same[0]["request"]
        elif near:
            item["possible_mirror_of"] = near[0]["request"]
    asked: dict[str, str] = {}
    stems: dict[str, str] = {}
    for item in items:
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


CLASSES = ("owner-decision", "plan-settleable", "repeated", "unresolved", "native-permission")


def count(handoffs: list[Path], db: Path, seconds: float) -> dict:
    deadline = time.monotonic() + seconds
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    # The bound holds inside a query too: SQLite abandons it once the deadline passes.
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    out = {"db": str(db), "bound_seconds": seconds, "complete": True, "runs": []}
    for handoff in handoffs:
        if time.monotonic() > deadline:
            out["complete"] = False
            out["runs"].append({"handoff": str(handoff), "skipped": "the time bound was reached first"})
            continue
        run = load_run(handoff)
        try:
            items = correct(read_items(connection, run), deadline)
        except (OutOfTime, sqlite3.OperationalError) as exc:
            if isinstance(exc, sqlite3.OperationalError) and time.monotonic() <= deadline:
                raise
            out["complete"] = False
            out["runs"].append({"handoff": str(handoff), "skipped": f"the time bound was reached while it was {'classed' if isinstance(exc, OutOfTime) else 'read'}"})
            continue
        old: dict[str, int] = {}
        for item in items:
            old[old_class(item["kind"], item["_text"])] = old.get(old_class(item["kind"], item["_text"]), 0) + 1
        corrected = {name: sum(1 for i in items if i["class"] == name) for name in CLASSES}
        out["runs"].append({
            "run": run["id"], "handoff": run["handoff"], "conversations": len(run["conversations"]),
            "from": run["start"].isoformat(timespec="minutes"), "to": run["end"].isoformat(timespec="minutes"),
            "old_count": {"total": len(items), **{k: old.get(k, 0) for k in ("his", "push", "plan", "unknown")}},
            "corrected_count": {"questions_asked": sum(corrected[c] for c in CLASSES[:4]), **corrected,
                                "mirrors_folded": sum(1 for i in items if i["class"] == "mirror"),
                                "possible_mirrors_kept": sum(1 for i in items if i["possible_mirror_of"])},
            "items": [{"request": i["request"][:8], "opened": i["opened"][:16], "kind": i["kind"], "class": i["class"],
                       **({"mirror_of": i["mirror_of"][:8]} if i["mirror_of"] else {}),
                       **({"possible_mirror_of": i["possible_mirror_of"][:8]} if i["possible_mirror_of"] else {}),
                       **({"repeats": i["repeats"][:8]} if i.get("repeats") else {})} for i in items],
            "_items": items})
    return out


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
    print("COVERAGE: complete" if result["complete"] else "COVERAGE: partial, the time bound was reached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
