#!/usr/bin/env python3
# MODULE: night_card.py - compose one departure card from fresh BMN facts and remaining work
"""Compose the run's one departure card from fresh BMN facts and its remaining work.

Usage: night_card.py --run ID --epic N --project PATH --remaining FILE --key K [--dry-run]
FILE has title, scope, limits ({name, boundary, uses, reason}), access ({name,
command, reason}), actions (allowed card terms), and nothing_reason. Limit
requests describe remaining expected uses, never past uses. An expected PR or
push is supplied as an action only when it names a concrete target.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def compose(facts, remaining, project, epic):
    """Return a card or a reasoned empty answer with the named conflicting facts."""
    plan, prs = facts["plan"], facts["pullRequests"]
    terms = []
    waits = []
    # Uses add within an allowance bucket. Per-boundary limits share one value across buckets.
    demands = {}
    proposed = {}
    local_raises = {}
    limits = {entry["name"]: entry for entry in plan["limits"]}
    for need in remaining.get("limits", []):
        name = need["name"]
        limit = limits.get(name)
        if limit is None:
            waits.append(f"BMN has no verified allowance for {name}. Check the recorded plan.")
            continue
        boundary = None if limit["per"] == "epic" else need["boundary"]
        demand = demands.setdefault((name, boundary), {"uses": 0, "reasons": []})
        demand["uses"] += need["uses"]
        if need["reason"] not in demand["reasons"]:
            demand["reasons"].append(need["reason"])
    for (name, boundary), demand in demands.items():
        limit = limits[name]
        available = limit if boundary is None else next(
            (use for use in limit["boundaries"] if use["boundary"] == boundary), None)
        if available is None or available["left"] is None or plan["state"] != "recorded":
            waits.append(f"BMN could not verify what remains of {name}. Check the recorded plan and ledger.")
            continue
        if available["left"] >= demand["uses"]:
            continue
        new_value = available["used"] + demand["uses"]
        ceiling = limit["ceiling"] if limit["ceiling"] is not None else limit["value"]
        if new_value <= ceiling:
            local_raises[name] = max(local_raises.get(name, 0), new_value)
            continue
        if new_value <= proposed.get(name, {}).get("to", 0):
            continue
        proposed[name] = dict(kind="limit", name=name, project=project, epic=epic,
                              **{"from": limit["value"], "to": new_value, "reason": " · ".join(demand["reasons"])})
    terms.extend(proposed.values())
    terms.extend(dict(kind="access", name=item["name"], command=item["command"], reason=item["reason"])
                 for item in remaining.get("access", []))
    for name, amount in local_raises.items():
        if name not in proposed:
            waits.append(f"Read the allowance token and use bmn plan allow {epic} limits.{name}.limit={amount} within the ceiling.")
    merge_actions = [term for term in remaining.get("actions", []) if term["kind"] == "merge"]
    explicit = {(term["repository"].lower(), term.get("pr")): term for term in merge_actions}
    for pr in prs["items"] if prs["state"] == "read" else []:
        identity = (pr["repository"].lower(), pr["number"])
        supplied = explicit.pop(identity, None)
        # The normal policy can merge when green. Pending checks are a wait, not a request for wider power.
        if pr["mayMerge"] is not False or pr["policy"] not in ("prs-only", "asks-owner"):
            continue
        why = (
            supplied["reason"] if supplied is not None and supplied.get("headSha") == pr["headSha"]
            else f"PR {pr['number']} into {pr['base']} needs your merge approval"
        )
        terms.append(dict(kind="merge", repository=pr["repository"], pr=pr["number"], headSha=pr["headSha"],
                          proposed="pr", reason=why))
    if explicit:
        waits.append("A requested merge had no verified open head. Read BMN’s pull request facts before asking for that merge.")
    if plan["state"] == "unknown" or prs["state"] == "unknown":
        waits.append("BMN could not confirm all facts. Keep the checks in your run log.")
    terms.extend(term for term in remaining.get("actions", []) if term["kind"] != "merge")
    if len(terms) > 8:
        raise ValueError("The run needs more than eight lines. Prioritize the needed lines and log those that must wait.")
    if terms:
        return {"title": remaining["title"], "scope": remaining["scope"], "terms": terms,
                **({"waits": list(dict.fromkeys(waits))} if waits else {})}
    if waits:
        raise ValueError(" ".join(dict.fromkeys(waits)))
    reason = remaining.get("nothing_reason", "").strip()
    if not reason or len(reason) > 300 or any(ord(ch) < 32 or ord(ch) == 127 for ch in reason):
        raise ValueError("Give the reason nothing remains to ask in one line of 1–300 characters.")
    explained = set(remaining.get("despite", []))
    conflicts = {fact["id"] for fact in facts["conflicts"]}
    if not conflicts <= explained:
        raise ValueError("Explain each conflict that needs no line: " + ", ".join(sorted(conflicts - explained)))
    return {"title": remaining["title"], "scope": remaining["scope"], "nothing": True,
            "reason": reason, "despite": sorted(conflicts)}


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--run", required=True)
    args.add_argument("--epic", required=True, type=int)
    args.add_argument("--project", type=Path, default=Path.cwd())
    args.add_argument("--remaining", type=Path, required=True)
    args.add_argument("--key", required=True)
    args.add_argument("--dry-run", action="store_true")
    options = args.parse_args()
    project = str(options.project.resolve())
    try:
        checked = subprocess.run(["bmn", "grant", "facts", "--run", options.run, "--epic", str(options.epic),
                                  "--project", project, "--json"], cwd=project, capture_output=True, text=True, check=True, timeout=30)
        remaining = json.loads(options.remaining.read_text())
        card = compose(json.loads(checked.stdout), remaining, project, options.epic)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        if isinstance(error, (ValueError, KeyError)):
            print(f"Departure card waits: {error}", file=sys.stderr)
        else:
            print("BMN or the remaining-work file could not be read. Keep the checks in your run log.", file=sys.stderr)
        return 1
    if options.dry_run:
        print(json.dumps(card, indent=2))
        return 0
    for notice in card.pop("waits", []):
        print(notice, file=sys.stderr)
    command = ["bmn", "grant", "ask", "--run", options.run, "--key", options.key]
    if card.get("nothing"):
        command += ["--nothing", "--title", card["title"], "--scope", card["scope"], "--reason", card["reason"]]
        for fact in card["despite"]:
            command += ["--despite", fact]
        return subprocess.run(command, cwd=project).returncode
    return subprocess.run(command + ["--card-file", "-"], input=json.dumps(card), text=True, cwd=project).returncode


if __name__ == "__main__":
    sys.exit(main())
