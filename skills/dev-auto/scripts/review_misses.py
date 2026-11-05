#!/usr/bin/env python3
# MODULE: review_misses.py - BMN Epic 105.5: per ProjectP ticket, whether the agent review ran and what people or PROD flagged, read-only and bounded
"""List, per ticket, whether the agent review ran and what people or PROD flagged, read-only and bounded.

Usage: review_misses.py --owner OWNER --since YYYY-MM-DD [--author LOGIN] [--lessons PATH] [--seconds N] [--json]

Pull requests created or closed since DATE are grouped by the `T<N>` in their title, else listed alone. Each one
is docs-only when all its files end in `.md` or sit under `docs/`, else eligible. It is reviewed only when it holds
the record comment, whose first line starts `Agent review (<tool>:review) at <sha12>, final <sha12>:`; a pull
request without it is not reviewed, whatever else happened on it.

Candidates are events a person should look at, never misses: CHANGES_REQUESTED or a line comment by a person other
than its author, and the `release:blocked` label, even one removed since, each after the review comment (on a pull
request with no review comment, all of them), and a revert naming the pull request. Only a lessons-file line starting `escape:` that links
a listed pull request counts as a confirmed miss. Added `MODULE` banner lines are counted beside them.

It only reads through `gh` and stops after --seconds (180), naming the repositories it covered and any it did not.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import sys
import time

SEARCH_LIMIT = 1000
REVERT_LIMIT = 200
WORKERS = 8
RECORD = re.compile(r"^Agent review \([^()\s]+:review\) at ([0-9a-f]{12}), final ([0-9a-f]{12}):")
TICKET = re.compile(r"\bT(\d+)\b", re.I)
BANNER = re.compile(r"^\+\s*\W{1,4}\s*(?:region\s+)?MODULE:")
PULL_LINK = re.compile(r"github\.com/([^/\s]+/[^/\s]+)/pull/(\d+)")
LESSONS_NAME = Path(".claude") / "review-lessons.md"


def default_lessons(start: Path) -> Path:
    """The nearest project lessons file from START upward, else the path it would have there."""
    for folder in (start, *start.parents):
        if (folder / LESSONS_NAME).is_file():
            return folder / LESSONS_NAME
    return start / LESSONS_NAME


class OutOfTime(Exception):
    pass


class ReadFailed(Exception):
    pass


def gh(args: list[str], deadline: float) -> object:
    """One read through gh, JSON back; a paginated answer's arrays come back as one list."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise OutOfTime
    try:
        run = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=left, check=False)
    except subprocess.TimeoutExpired as error:
        raise OutOfTime from error
    except OSError as error:
        raise ReadFailed(str(error)) from error
    if run.returncode:
        raise ReadFailed(f"{' '.join(args[:3])}: {(run.stderr or run.stdout).strip()[:200]}")
    decoder, text, position, parts = json.JSONDecoder(), run.stdout, 0, []
    while position < len(text):
        if text[position].isspace():
            position += 1
            continue
        part, position = decoder.raw_decode(text, position)
        parts.append(part)
    if len(parts) == 1:
        return parts[0]
    return [item for part in parts for item in (part if isinstance(part, list) else [part])]


def person(user: dict | None, author: str) -> bool:
    if not user or user.get("type") == "Bot" or str(user.get("login", "")).endswith("[bot]"):
        return False
    return user.get("login") != author


def later_events(reviews: list[dict], line_comments: list[dict], author: str, since: str) -> list[dict]:
    events = []
    for review in reviews:
        at = review.get("submitted_at") or ""
        if review.get("state") == "CHANGES_REQUESTED" and person(review.get("user"), author) and at > since:
            events.append({"kind": "changes-requested", "by": review["user"]["login"], "at": at, "url": review.get("html_url", "")})
    for comment in line_comments:
        at = comment.get("created_at") or ""
        if person(comment.get("user"), author) and at > since:
            events.append({"kind": "line-comment", "by": comment["user"]["login"], "at": at, "url": comment.get("html_url", "")})
    return sorted(events, key=lambda event: event["at"])


def review_eligible(names: list[str]) -> bool:
    """Whether a PR with these changed files takes the review: not when every file is `.md`, or under `docs/` or `plan/` (BMN Epic 106 D21)."""
    return not names or not all(name.endswith(".md") or name.startswith(("docs/", "plan/")) for name in names)


def read_pr(found: dict, deadline: float) -> dict:
    repo = found["repository"]["nameWithOwner"]
    number = found["number"]
    author = (found.get("author") or {}).get("login", "")

    def rest(tail: str) -> list[dict]:
        answer = gh(["api", "--paginate", f"repos/{repo}/{tail}?per_page=100"], deadline)
        return answer if isinstance(answer, list) else []

    files = rest(f"pulls/{number}/files")
    comments = rest(f"issues/{number}/comments")
    reviews = rest(f"pulls/{number}/reviews")
    line_comments = rest(f"pulls/{number}/comments")
    issue_events = rest(f"issues/{number}/events")
    names = [str(file.get("filename", "")) for file in files]
    docs_only = not review_eligible(names)
    records = [(comment, RECORD.match(str(comment.get("body", "")))) for comment in comments]
    records = [(comment, match) for comment, match in records if match]
    comment, match = records[-1] if records else (None, None)
    banner_lines = sum(1 for file in files for line in str(file.get("patch", "")).splitlines() if BANNER.match(line))
    unread_patches = sum(1 for file in files if file.get("additions") and "patch" not in file)
    since = comment.get("created_at", "") if comment else ""
    events = later_events(reviews, line_comments, author, since)
    labeled = [str(event.get("created_at", "")) for event in issue_events
               if event.get("event") == "labeled" and (event.get("label") or {}).get("name") == "release:blocked"]
    if not labeled and any(label.get("name") == "release:blocked" for label in found.get("labels") or []):
        labeled = [str(found.get("updatedAt", ""))]
    later = [at for at in labeled if at > since]
    if later:
        events.append({"kind": "release:blocked", "by": "", "at": min(later), "url": found.get("url", "")})
    return {"repo": repo, "number": number, "url": found.get("url", ""), "title": found.get("title", ""), "state": found.get("state", ""),
            "author": author, "docs_only": docs_only, "eligible": not docs_only, "reviewed": bool(match),
            "reviewed_head": match.group(1) if match else None, "final_head": match.group(2) if match else None,
            "comment": comment.get("html_url") if comment else None, "banner_lines": banner_lines, "unread_patches": unread_patches, "events": events}


def revert_targets(owner: str, since: str, deadline: float) -> tuple[dict[tuple[str, int], str], list[str]]:
    """Which pull requests a revert names: a pull request titled or a commit message starting `Revert`."""
    targets: dict[tuple[str, int], str] = {}
    gaps = []

    def note(repo: str, text: str, url: str) -> None:
        for number in re.findall(r"#(\d+)\b", text):
            targets.setdefault((repo, int(number)), url)
        for linked_repo, number in PULL_LINK.findall(text):
            targets.setdefault((linked_repo, int(number)), url)

    try:
        pulls = gh(["search", "prs", "Revert in:title", "--owner", owner, "--updated", f">={since}", "--limit", str(REVERT_LIMIT),
                    "--json", "repository,title,body,url"], deadline)
        for pull in pulls if isinstance(pulls, list) else []:
            if str(pull.get("title", "")).lower().startswith("revert"):
                note(pull["repository"]["nameWithOwner"], f"{pull.get('title', '')}\n{pull.get('body', '')}", pull.get("url", ""))
    except ReadFailed as error:
        gaps.append(f"revert pull requests: {error}")
    try:
        commits = gh(["search", "commits", "Revert", "--owner", owner, "--committer-date", f">={since}", "--limit", str(REVERT_LIMIT),
                      "--json", "repository,commit,url"], deadline)
        for commit in commits if isinstance(commits, list) else []:
            message = str((commit.get("commit") or {}).get("message", ""))
            if message.lower().startswith("revert"):
                note(commit["repository"].get("fullName", ""), message, commit.get("url", ""))
    except ReadFailed as error:
        gaps.append(f"revert commits: {error}")
    return targets, gaps


def confirmed(lessons: Path, listed: set[tuple[str, int]]) -> list[str]:
    try:
        lines = lessons.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [line for line in lines if line.startswith("escape:")
            and any((repo, int(number)) in listed for repo, number in PULL_LINK.findall(line))]


def report(owner: str, since: str, author: str | None, lessons: Path, seconds: float) -> dict:
    started = time.monotonic()
    deadline = started + seconds
    query = ["search", "prs", "--owner", owner, "--updated", f">={since}", "--limit", str(SEARCH_LIMIT),
             "--json", "repository,number,title,url,state,author,createdAt,closedAt,updatedAt,labels"]
    if author:
        query += ["--author", author]
    coverage: dict = {"covered": [], "not_covered": [], "gaps": [], "truncated": False}
    found_prs: list[dict] = []
    try:
        answer = gh(query, deadline)
        found_prs = answer if isinstance(answer, list) else []
        coverage["truncated"] = len(found_prs) >= SEARCH_LIMIT
    except (OutOfTime, ReadFailed) as error:
        coverage["not_covered"].append(owner)
        coverage["gaps"].append(f"search: {error or 'out of time'}")
    wanted = [pr for pr in found_prs if pr.get("state") != "closed"
              and (str(pr.get("createdAt", ""))[:10] >= since or str(pr.get("closedAt") or "")[:10] >= since)]

    def read(pr: dict) -> tuple[dict, dict | str]:
        try:
            return pr, read_pr(pr, deadline)
        except OutOfTime:
            return pr, "out of time"
        except ReadFailed as error:
            return pr, str(error)

    reverts: dict[tuple[str, int], str] = {}
    if wanted:
        try:
            reverts, gaps = revert_targets(owner, since, deadline)
            coverage["gaps"] += gaps
        except OutOfTime:
            coverage["gaps"].append("reverts: out of time")
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(read, wanted))
    read_prs = [result for _, result in results if isinstance(result, dict)]
    unread = [(pr, result) for pr, result in results if not isinstance(result, dict)]
    for pr in read_prs:
        target = reverts.get((pr["repo"], pr["number"]))
        if target:
            pr["events"].append({"kind": "revert", "by": "", "at": "", "url": target})
    repositories = {pr["repository"]["nameWithOwner"] for pr in wanted}
    failed = {pr["repository"]["nameWithOwner"] for pr, _ in unread}
    coverage["covered"] = sorted(repositories - failed)
    coverage["not_covered"] += sorted(failed)
    coverage["gaps"] += [f"{pr['repository']['nameWithOwner']}#{pr['number']}: {why}" for pr, why in unread]
    groups: dict[str, list[dict]] = {}
    for pr in read_prs:
        ticket = TICKET.search(pr["title"])
        groups.setdefault(f"T{ticket.group(1)}" if ticket else f"{pr['repo']}#{pr['number']}", []).append(pr)
    listed = {(pr["repo"], pr["number"]) for pr in read_prs}
    misses = confirmed(lessons, listed)
    eligible = [pr for pr in read_prs if pr["eligible"]]
    totals = {"groups": len(groups), "eligible": len(eligible), "reviewed": sum(1 for pr in eligible if pr["reviewed"]),
              "candidates": sum(len(pr["events"]) for pr in read_prs), "banners_added": sum(pr["banner_lines"] for pr in read_prs),
              "confirmed_misses": len(misses)}
    return {"owner": owner, "since": since, "author": author, "coverage": coverage,
            "groups": [{"group": name, "prs": sorted(prs, key=lambda pr: (pr["repo"], pr["number"]))} for name, prs in sorted(groups.items())],
            "totals": totals, "confirmed": misses, "seconds": round(time.monotonic() - started, 1)}


def text(result: dict) -> str:
    lines = []
    for group in result["groups"]:
        lines.append(group["group"])
        for pr in group["prs"]:
            if pr["docs_only"]:
                review = "docs-only, skipped"
            elif pr["reviewed"]:
                review = f"reviewed {pr['reviewed_head']}, final {pr['final_head']}"
            else:
                review = "eligible, not reviewed"
            banners = f"; {pr['banner_lines']} banner lines added" if pr["banner_lines"] else ""
            unread = f"; {pr['unread_patches']} files too large to read for banners" if pr["unread_patches"] else ""
            lines.append(f"  {pr['repo']}#{pr['number']} ({pr['state']}): {review}{banners}{unread}")
            lines.extend(f"    candidate: {event['kind']} {event['by']} {event['url']}".rstrip() for event in pr["events"])
    coverage = result["coverage"]
    lines.append(f"Covered: {', '.join(coverage['covered']) or 'none'}.")
    lines.append(f"Not covered: {', '.join(coverage['not_covered']) or 'none'}.")
    if coverage["truncated"]:
        lines.append(f"The search stopped at its {SEARCH_LIMIT} results: narrow --since or --author.")
    lines.extend(f"Gap: {gap}" for gap in coverage["gaps"])
    totals = result["totals"]
    lines.append(f"Totals: groups {totals['groups']}, eligible {totals['eligible']}, reviewed {totals['reviewed']}, candidates {totals['candidates']}, "
                 f"banners added {totals['banners_added']}, confirmed misses {totals['confirmed_misses']}.")
    lines.append("Candidates are for a person to read, never misses; only an `escape:` line in the lessons file confirms one.")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if {"-h", "--help"} & set(argv):
        print(__doc__)
        return 0
    names = ("--owner", "--since", "--author", "--lessons", "--seconds")
    values = {name: argv[argv.index(name) + 1] for name in names if name in argv and argv.index(name) + 1 < len(argv)}
    if "--owner" not in values or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", values.get("--since", "")):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        seconds = float(values.get("--seconds", 180))
    except ValueError:
        print(__doc__, file=sys.stderr)
        return 2
    result = report(values["--owner"], values["--since"], values.get("--author"), Path(values["--lessons"]) if "--lessons" in values else default_lessons(Path.cwd()), seconds)
    print(json.dumps(result, indent=1) if "--json" in argv else text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
