#!/usr/bin/env python3
# MODULE: review_lenses.py - BMN Epic 105.3: asks every lens a ProjectP review pack recommends through bmn team ask, Busy bounded, and ends with answers or BLOCKED
"""Ask every lens a review-tools review pack recommends, one literal command for Codex and Claude Code.

Usage: review_lenses.py --pack PACK.md --skill SKILL_DIR --project DIR [--lessons PATH] [--intent TEXT]
                        [--busy-seconds N] [--seconds N] [--retry-seconds N] [--poll-seconds N]

The lens list comes from pack.json beside the pack, so a lens cannot be dropped. Routes follow BMN Epic 105 D3:
bugs and architect on Astra at medium, one-of-each and platform on Luna at max. Busy (exit 14) is retried with the
same key every minute for up to 30 minutes; other sessions can hold the slots unseen. Every subprocess has its own
deadline and the whole run has one (an hour). Only asks this run started are ever stopped, and only at the deadline.

Each answer must be the JSON object rules.md describes; it is written to <pack dir>/lenses/<lens>.json. The run
ends `ANSWERED <n> of <n>` with exit 0, or `BLOCKED: <lens>: <reason>` with exit 1; 2 is a usage error. Triage,
policy, the comment and the line stay with the lead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROUTES = {"bugs": ("astra", "medium"), "architect": ("astra", "medium"), "one-of-each": ("luna", "max"), "platform": ("luna", "max")}
DEFAULT_LESSONS = Path.home() / "code" / "ProjectP" / ".claude" / "review-lessons.md"
BUSY = 14
RUNNING = {"accepted", "starting", "running", "queued", "stopping"}
CALL_SECONDS = 60
TIME_LIMIT_MINUTES = 45
OPTIONS = {"--pack", "--skill", "--project", "--lessons", "--intent", "--busy-seconds", "--seconds", "--retry-seconds", "--poll-seconds"}


@dataclass
class Lens:
    name: str
    key: str
    run: str = ""
    next_try: float = 0.0
    answer: Path | None = None
    reason: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return bool(self.answer or self.reason)


def call(*args: str) -> tuple[int | None, dict[str, object], str]:
    """One bmn call under its own deadline; a call that hangs or cannot start is None, never a wait without end."""
    try:
        done = subprocess.run(["bmn", *args], capture_output=True, text=True, timeout=CALL_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, {}, type(error).__name__
    try:
        data = json.loads(done.stdout)
    except json.JSONDecodeError:
        data = {}
    return done.returncode, data if isinstance(data, dict) else {}, " ".join((done.stderr or done.stdout).split())[:300]


def question(lens: str, skill: Path, pack: Path, intent: str) -> str:
    return (
        f"You are the `{lens}` lens of a ProjectP code review. Read fully, in order: `{skill}/references/rules.md`, "
        f"`{skill}/references/lenses/{lens}.md`, `{pack}`.\nTicket intent: {intent}\n"
        "Review the whole task through your lens only. Do it yourself: never start sub-agents or any other agent. "
        "Change nothing. Your last message is only the JSON object `rules.md` describes.\n"
    )


def parsed(answer: object, lens: str) -> dict[str, list[object] | str] | None:
    """The answer as the object rules.md describes, a code fence around it allowed; anything else is no answer."""
    text = str(answer or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("lens") != lens or not isinstance(data.get("findings"), list):
        return None
    return data


def ask(item: Lens, skill: Path, pack: Path, project: Path, lessons: Path, intent: str, now: float, busy_until: float, retry: float) -> None:
    agent, effort = ROUTES[item.name]
    code, data, detail = call(
        "team", "ask", "--role", "focused-reviewer", "--agent", agent, "--effort", effort, "--project", str(project),
        "--file", str(skill / "references" / "rules.md"), "--file", str(skill / "references" / "lenses" / f"{item.name}.md"),
        "--file", str(lessons), "--question", question(item.name, skill, pack, intent), "--key", item.key,
        "--time-limit", str(TIME_LIMIT_MINUTES), "--background", "--json",
    )
    if code == 0 and data.get("id"):
        item.run = str(data["id"])
        print(f"ASKED {item.name} on {agent}/{effort}: {item.run}", flush=True)
    elif code == BUSY or code is None:
        if now >= busy_until:
            item.reason = "busy past the limit" if code == BUSY else f"bmn did not answer ({detail})"
        else:
            item.next_try = now + retry
            print(f"WAIT {item.name}: {'busy' if code == BUSY else detail}", flush=True)
    else:
        refusal = data.get("refusal")
        reason = refusal.get("reason") if isinstance(refusal, dict) else None
        item.reason = f"bmn team ask exit {code}: {reason or detail}"


def poll(item: Lens, folder: Path, now: float, retry: float) -> None:
    code, data, detail = call("team", "asks", "show", item.run, "--json")
    state = str(data.get("state", ""))
    if code is None or (code == 0 and state in RUNNING) or not state:
        if not state and code not in (None, 0):
            item.reason = f"bmn team asks show exit {code}: {detail}"
        item.next_try = now + retry
        return
    if state != "answered":
        item.reason = f"the ask ended {state}, exit {data.get('exit')}"
        return
    answer = parsed(data.get("answer"), item.name)
    if answer is None:
        item.reason = f"the answer of {item.run} is not the object rules.md describes"
        return
    target = folder / f"{item.name}.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(answer, indent=1), encoding="utf-8")
    temp.replace(target)
    if json.loads(target.read_text(encoding="utf-8")) != answer:
        item.reason = f"the answer file {target} did not read back equal"
        return
    item.answer = target
    print(f"ANSWERED {item.name}: {len(answer['findings'])} findings, {target} ({item.run})", flush=True)


def arguments(argv: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    index = 0
    while index < len(argv):
        name = argv[index]
        if name not in OPTIONS or index + 1 >= len(argv):
            raise ValueError(f"unknown or incomplete option {name}")
        values[name] = argv[index + 1]
        index += 2
    for needed in ("--pack", "--skill", "--project"):
        if needed not in values:
            raise ValueError(f"{needed} is required")
    return values


def lenses_of(pack: Path, stamp: str) -> list[Lens]:
    listed = json.loads((pack.parent / "pack.json").read_text(encoding="utf-8")).get("lenses")
    if not isinstance(listed, list) or not listed:
        raise ValueError("pack.json lists no lenses")
    unknown = [name for name in listed if name not in ROUTES]
    if unknown:
        raise ValueError(f"no route for {', '.join(map(str, unknown))}")
    digest = hashlib.sha256(pack.read_bytes()).hexdigest()[:12]
    return [Lens(name, f"{stamp}-review-{digest}-{name}") for name in listed]


def main(argv: list[str]) -> int:
    try:
        values = arguments(argv)
        pack = Path(values["--pack"]).expanduser().resolve()
        skill = Path(values["--skill"]).expanduser().resolve()
        project = Path(values["--project"]).expanduser().resolve()
        lessons = Path(values.get("--lessons", DEFAULT_LESSONS)).expanduser().resolve()
        intent = values.get("--intent", "see PR descriptions")
        busy_seconds = float(values.get("--busy-seconds", 1800))
        seconds = float(values.get("--seconds", 3600))
        retry = float(values.get("--retry-seconds", 60))
        wait = float(values.get("--poll-seconds", 15))
    except ValueError as error:
        print(f"usage: {error}", file=sys.stderr)
        return 2
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    try:
        items = lenses_of(pack, stamp)
        for item in items:
            for needed in (skill / "references" / "rules.md", skill / "references" / "lenses" / f"{item.name}.md", lessons):
                if not needed.is_file():
                    raise ValueError(f"missing {needed}")
        if not project.is_dir():
            raise ValueError(f"missing {project}")
        folder = pack.parent / "lenses"
        folder.mkdir(exist_ok=True)
    except (OSError, ValueError) as error:
        print(f"BLOCKED: {error}", flush=True)
        return 1
    start = time.monotonic()
    busy_until, deadline = start + busy_seconds, start + seconds
    while not all(item.done for item in items):
        now = time.monotonic()
        if now >= deadline:
            for item in items:
                if item.done:
                    continue
                if item.run:
                    call("team", "asks", "stop", item.run, "--json")  # started by this run, so this run may stop it
                item.reason = "no answer by the deadline"
            break
        for item in items:
            if item.done or now < item.next_try:
                continue
            if item.run:
                poll(item, folder, now, wait)
            else:
                ask(item, skill, pack, project, lessons, intent, now, busy_until, retry)
        pending = [item.next_try for item in items if not item.done]
        if pending:
            time.sleep(max(0.05, min(min(pending), deadline) - time.monotonic()))
    failed = [item for item in items if item.reason]
    for item in failed:
        print(f"BLOCKED: {item.name}: {item.reason}", flush=True)
    if failed:
        return 1
    print(f"ANSWERED {len(items)} of {len(items)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
