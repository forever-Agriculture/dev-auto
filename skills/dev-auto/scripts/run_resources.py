# MODULE: run_resources.py - read-only launch-identity and worktree inventories
"""Read-only inventories for a run; discovery never authorizes stopping or removing."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess


def command(argv: list[str]) -> str:
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=30).stdout


def under(value: str, root: Path) -> bool:
    return value == str(root) or value.startswith(str(root) + "/")


def process(pid: int, proc: Path = Path("/proc"), recorded: bool = False) -> dict | None:
    try:
        path = proc / str(pid)
        if path.stat().st_uid != os.getuid() and not recorded:
            return None
        stat = (path / "stat").read_text().rsplit(")", 1)[1].split()
        if stat[0] == "Z":
            return None
        args = (path / "cmdline").read_bytes().decode(errors="replace").strip("\0").split("\0")
        try:
            cwd = str((path / "cwd").readlink())
        except FileNotFoundError:
            cwd = ""
        except PermissionError:
            if not recorded:
                raise
            cwd = ""  # a recorded identity needs no path inference
        return {"kind": "process", "pid": pid, "start_ticks": stat[19],
                "ppid": int(stat[1]), "args": args, "cwd": cwd}
    except (FileNotFoundError, ProcessLookupError):
        return None  # disappeared during the scan


def started(body: str) -> list[dict]:
    """Each bullet in ## Started is one JSON launch identity, or `none`."""
    entries = []
    section = False
    for line in body.splitlines():
        if line.startswith("## "):
            section = line == "## Started"
        elif section and line.startswith("- ") and line[2:].strip().lower() != "none":
            entry = json.loads(line[2:])
            if not isinstance(entry, dict) or not isinstance(entry.get("command"), str):
                raise ValueError("Started entries need a command")
            if entry.get("kind") == "process":
                if type(entry.get("pid")) is not int or entry["pid"] <= 0 or not str(entry.get("start_ticks", "")).isdigit():
                    raise ValueError("Started process needs pid and start_ticks")
            elif entry.get("kind") == "container":
                if not re.fullmatch(r"[a-f0-9]{64}", entry.get("id", "")) or not entry.get("name"):
                    raise ValueError("Started container needs full id and name")
            else:
                raise ValueError("Started entry kind must be process or container")
            entries.append(entry)
    return entries


def safe_command(args: list[str]) -> str:
    # Positional operands, shell scripts and headers may contain private text or secrets.
    # The launch record, not this process listing, holds the full reviewed command.
    if not args:
        return "[command unavailable]"
    options = [arg.split("=", 1)[0] if re.fullmatch(r"--?[A-Za-z][A-Za-z-]*(?:=.*)?", arg)
               else "[argument]" for arg in args[1:]]
    return shlex.join([Path(args[0]).name, *options])


def is_bmn(item: dict) -> bool:
    args = item["args"]
    return bool(args and Path(args[0]).name.lower() in ("bmn", "bmn-app"))


def inventory(root: Path, entries: list[dict], proc: Path = Path("/proc"),
              containers: list[dict] | None = None,
              warnings: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    excluded = set()
    pid = os.getpid()
    while pid and pid not in excluded:
        excluded.add(pid)
        # Parent identity needs stat only: a protected cwd must not truncate exclusion.
        try:
            stat = (proc / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
            pid = int(stat[1])
        except (FileNotFoundError, ProcessLookupError):
            break
    launches = {e["pid"]: e for e in entries if e["kind"] == "process"}
    owned, candidates = [], []
    for path in proc.iterdir():
        if not path.name.isdigit() or int(path.name) in excluded:
            continue
        try:
            item = process(int(path.name), proc, recorded=int(path.name) in launches)
        except PermissionError:
            if warnings is None:
                raise
            warnings.append(f"pid={path.name}: process path/command unreadable")
            continue
        if item is None or is_bmn(item):
            continue
        launch = launches.get(item["pid"])
        if launch and str(launch["start_ticks"]) == item["start_ticks"]:
            item["keep"] = launch.get("keep", "")
            owned.append(item)
        elif under(item["cwd"], root) or any(re.search(r"(?<![\w/.-])" + re.escape(str(root)) + r"(?=/|\s|['\"]|$)", a) for a in item["args"]):
            candidates.append(item)
    launches_by_id = {e["id"]: e for e in entries if e["kind"] == "container"}
    for container in containers or []:
        if not container.get("State", {}).get("Running"):
            continue
        launch = launches_by_id.get(container["Id"])
        item = {"kind": "container", "id": container["Id"], "name": container["Name"].lstrip("/"),
                "started_at": container["State"].get("StartedAt", "unknown"),
                "args": [container.get("Path", ""), *container.get("Args", [])]}
        if launch and launch["name"] == item["name"]:
            item["keep"] = launch.get("keep", "")
            owned.append(item)
        elif any(under(m.get("Source", ""), root) for m in container.get("Mounts", [])):
            candidates.append(item)
    return owned, candidates


def leftovers(root: Path) -> int:
    root = root.resolve()
    try:
        entries = started((root / ".dev-auto/handoff.md").read_text())
        containers = []
        warnings = []
        if shutil.which("docker"):
            try:
                ids = command(["docker", "ps", "--no-trunc", "--format", "{{.ID}}"]).split()
                if ids:
                    containers = json.loads(command(["docker", "inspect", *ids]))
            except (OSError, ValueError, subprocess.SubprocessError):
                warnings.append("container discovery unavailable")
        else:
            warnings.append("docker unavailable; container discovery unverified")
        owned, candidates = inventory(root, entries, containers=containers, warnings=warnings)
        uptime = float(Path("/proc/uptime").read_text().split()[0])
        ticks = os.sysconf("SC_CLK_TCK")
        for title, items in (("Owned", owned), ("Candidates", candidates)):
            print(title + ":")
            if not items:
                print("- none")
            for item in items:
                if item["kind"] == "process":
                    identity = f'pid={item["pid"]} start_ticks={item["start_ticks"]}'
                    age = f'{max(0, uptime - int(item["start_ticks"]) / ticks):.0f}s'
                else:
                    identity = f'{item["name"]} id={item["id"]}'
                    age = "since " + item["started_at"]
                keep = f' KEEP: {item["keep"]}' if item.get("keep") else ""
                print(f'- {identity}; age={age}; {safe_command(item["args"])}{keep}')
        for warning in warnings:
            print("UNABLE: " + warning + "; inventory partial, no changes made")
        return 2 if warnings else 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"UNABLE: leftovers inventory incomplete ({type(exc).__name__}); no changes made")
        return 2


def dirty_count(porcelain: str) -> int:
    records = iter(porcelain.split("\0"))
    count = 0
    for record in records:
        if record:
            count += 1
            if "R" in record[:2] or "C" in record[:2]:
                next(records, None)
    return count


def worktree_list(root: Path) -> list[dict]:
    """Every checkout of root's repository as `git worktree list --porcelain` names it, the default first."""
    listing = command(["git", "-C", str(root), "worktree", "list", "--porcelain", "-z"])
    return [dict(line.split(" ", 1) if " " in line else (line, "") for line in block.split("\0")) for block in listing.strip("\0").split("\0\0")]


def default_branch(root: Path) -> str | None:
    """One default-branch policy for inventory and authorized cleanup."""
    try:
        default = command(["git", "-C", str(root), "symbolic-ref", "refs/remotes/origin/HEAD"]).strip().replace("refs/remotes/origin/", "")
    except subprocess.CalledProcessError:
        branches = command(["git", "-C", str(root), "for-each-ref", "--format=%(refname:short)", "refs/heads/"]).splitlines()
        conventional = [b for b in branches if b in ("main", "master")]
        default = conventional[0] if len(conventional) == 1 else (branches[0] if len(branches) == 1 else None)
    return default


def worktrees(root: Path) -> int:
    from handoff_state import finished, status_fields
    try:
        listed = worktree_list(root)
        default = default_branch(root)
        default_ref = None
        if default:
            for ref in (f"refs/heads/{default}", f"refs/remotes/origin/{default}"):
                try:
                    command(["git", "-C", str(root), "rev-parse", "--verify", ref])
                    default_ref = ref
                    break
                except subprocess.CalledProcessError:
                    pass
        partial = False
        for values in listed:
            path = Path(values["worktree"])
            try:
                dirty = dirty_count(command(["git", "--no-optional-locks", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=all", "-z"]))
                size = int(command(["du", "-s", "--block-size=1", "--", str(path)]).split()[0])
                handoff = path / ".dev-auto/handoff.md"
                body = handoff.read_text() if handoff.exists() else ""
                statuses, _ = status_fields(body)
                status = statuses[0] if len(statuses) == 1 else "unknown"
                complete = finished(body)
                merged = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", values["HEAD"], default_ref], capture_output=True, timeout=30).returncode if default_ref else 1
                if merged not in (0, 1):
                    raise ValueError("cannot determine ancestry")
                branch = values.get("branch", "detached").removeprefix("refs/heads/")
                keep = dirty > 0 or not complete or merged != 0 or branch == default or "locked" in values
                print(json.dumps({"path": str(path), "branch": branch, "status": status,
                                  "ancestry": ("ancestor of " + default if merged == 0 else "not merged") if default_ref else "unknown default branch",
                                  "uncommitted": dirty, "bytes": size, "action": "keep" if keep else "may ask owner"}))
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                partial = True
                print(json.dumps({"path": str(path), "action": "keep", "error": "inventory unavailable"}))
        return 2 if partial else 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"UNABLE: worktree inventory incomplete ({type(exc).__name__}); no changes made")
        return 2
