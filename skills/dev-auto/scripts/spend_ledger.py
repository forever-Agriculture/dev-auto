#!/usr/bin/env python3
# MODULE: spend_ledger.py - BMN Epic 90.4: the go's money cap kept at every paid launch by one reservation ledger per plan and epic; 96.2: the go's extra repair rounds counted in the same ledger
"""Reserve a paid job's maximum against the epic's money cap before it starts; count the go's extra repair rounds.

Usage:
  spend_ledger.py open --epic N [--project P]             record the epic's go, its cap and its rounds; prints the budget id,
                                                          the go's identity and the rounds left at each boundary
  spend_ledger.py open --epic N --cap USD --source TEXT   an owner-stated cap for an epic with no go and no cap yet
  spend_ledger.py launch --budget B --job J --max USD [--direct] -- JOB_SCRIPT [ARGS...]
  spend_ledger.py settle --budget B --job J (--spent USD | --unknown)
  spend_ledger.py release --budget B --job J              the job never ran: its reservation is returned
  spend_ledger.py round --budget B --boundary STORY|epic --use-id ID   take one of the go's extra repair rounds
  spend_ledger.py status --budget B

One ledger per plan and epic, under $XDG_STATE_HOME/dev-auto/budgets/ (default ~/.local/state), outside every
worktree, shared by resumes, new leads and replacement runs: a plan is named by its repository's shared Git folder
and its path inside it, so every linked worktree finds the same ledger. The cap in force is the latest go's, and a
go older than (or unrelated to) the one recorded is refused; `none` refuses every paid launch. A reapproval never resets what was settled or reserved: it counts against the new cap. `launch`
reserves only when settled + outstanding reservations + this maximum stay within the cap, writing atomically under
a lock, then starts the job detached (`systemd-run --user`, as references/models.md runs paid jobs; `--direct`
starts it as a detached process instead). A refusal, an invalid amount or a missing maximum starts nothing and exits
non-zero; a retry under the same job id returns the first answer. An unknown outcome, including a launch whose
acknowledgement timed out, keeps its reservation until it is settled or released. The
ledger covers dev-auto's own paid launches, not every provider call.

The go's extra repair rounds per boundary (its Run needs) are counted here too, so every resume, replacement lead
and linked worktree of the epic sees the same rounds left (BMN 96.2). A boundary is one of the epic's stories at its
go (7.2) or `epic`, never a free name or an unplanned story a new run could pick again. `round` takes one under the
lock only while the latest go's rounds exceed those used at that boundary under every go: a reapproval refills
nothing used, and two runs cannot take the same round. A retry under the same use id returns the first answer.
Without a recorded go there are none; a go the ledger lacks although a handoff of the project's worktrees already
names it, or whose epic row is past ready, has its extra rounds counted as used (BMN 96 D9). Each `open`, `round`
and paid `launch` reads the go again: once the plan withdraws it (a row put back, a later hand go after `bmn plan
go` took over), the withdrawal is recorded and it gives no round and no paid launch until his next go.
"""
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EXIT_REFUSED, EXIT_USAGE = 1, 2
BUDGET_ID = re.compile(r"[0-9a-f]{16}-epic-\d+")
BOUNDARY = re.compile(r"(\d+)\.\d+|epic")


def budgets() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    path = base / "dev-auto" / "budgets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def amount(text: str | None) -> float | None:
    try:
        value = float(text) if text is not None else None
    except ValueError:
        return None
    return value if value is not None and math.isfinite(value) and value > 0 else None


class Ledger:
    """The budget file, read and written only while its lock is held."""

    def __init__(self, budget: str) -> None:
        if not BUDGET_ID.fullmatch(budget):
            raise ValueError(f"not a budget id: {budget}")
        self.path = budgets() / f"{budget}.json"
        self.lock = open(budgets() / f"{budget}.lock", "a+")

    def __enter__(self) -> dict:
        fcntl.flock(self.lock, fcntl.LOCK_EX)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"gos": [], "jobs": {}}
        self.data.setdefault("rounds", {})
        return self.data

    def save(self) -> None:
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".budget-")
        with os.fdopen(handle, "w") as out:
            json.dump(self.data, out, indent=1)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, self.path)

    def __exit__(self, *_: object) -> None:
        fcntl.flock(self.lock, fcntl.LOCK_UN)
        self.lock.close()


def plan_identity(plan_root: str) -> str:
    """The plan as every linked worktree sees it: its repository's shared Git folder and its path inside it."""
    root = Path(plan_root).resolve()
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel", "--git-common-dir"],
                             capture_output=True, text=True, timeout=10, check=True).stdout.splitlines()
        common = Path(out[1]) if Path(out[1]).is_absolute() else root / out[1]
        return f"{common.resolve()}::{root.relative_to(Path(out[0]).resolve())}"
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return str(root)  # not in Git: the folder itself


def go_follows(plan_root: str, earlier: str, later: str) -> bool:
    """Whether the go commit `later` comes after `earlier` in the plan's history."""
    try:
        return subprocess.run(["git", "-C", plan_root, "merge-base", "--is-ancestor", earlier, later],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def cap_in_force(data: dict) -> float | None:
    return data["gos"][-1]["cap"] if data["gos"] else None


def totals(data: dict) -> tuple[float, float]:
    jobs = data["jobs"].values()
    settled = sum(job.get("spent", 0.0) for job in jobs if job["state"] == "settled")
    outstanding = sum(job["max"] for job in jobs if job["state"] in ("reserved", "started", "unknown"))
    return settled, outstanding


def latest_go(data: dict) -> dict | None:
    """The go in force: the last one recorded, unless its withdrawal came after it."""
    for entry in reversed(data["gos"]):
        if entry.get("kind") == "withdrawn":
            return None
        if entry.get("kind") == "go":
            return entry
    return None


def withdraw(data: dict, go: dict, reason: str) -> None:
    """The plan no longer holds the go in force: no extra round and no paid launch until his next go (NFR1)."""
    data["gos"].append({"kind": "withdrawn", "commit": go["commit"], "cap": None, "reason": reason, "at": now()})


def go_now(data: dict, go: dict) -> tuple[str, str]:
    """The go in force read again from the plan: `stands`, `withdrawn` (the plan gives no GO), `newer` or `unreadable`, and why."""
    import run_needs
    try:
        needs = run_needs.run_needs(Path(data.get("project") or data["plan_root"]), int(data["epic"]))
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        return "unreadable", f"the plan cannot be read now: {exc}"
    if needs["state"] == "GO":
        return ("stands", "") if needs["go_commit"] == go["commit"] else ("newer", f"go {needs['go_commit'][:12]} is newer: open the ledger again")
    # Put back, or a later go that names no act (BMN 96 recheck): either way the go in force no longer stands.
    return "withdrawn", needs.get("reason") or needs["state"]


def rounds_used(data: dict, boundary: str) -> int:
    return sum(1 for use in data["rounds"].values() if use["answer"] == "TAKEN" and use["boundary"] == boundary)


def describe_go(data: dict) -> list[str]:
    """The go in force and the rounds it leaves at each boundary used so far, for the handoff's Go field."""
    go = latest_go(data)
    if go is None and data["gos"] and data["gos"][-1].get("kind") == "withdrawn":
        return [f"GO: withdrawn ({data['gos'][-1]['reason']}); no extra repair rounds and no paid launch until his next go"]
    if go is None:
        return ["GO: none recorded; no extra repair rounds (the invocation's allowance only)"]
    boundaries = sorted({use["boundary"] for use in data["rounds"].values() if use["answer"] == "TAKEN"})
    used = ", ".join(f"{b} {rounds_used(data, b)} used" for b in boundaries) or "none used"
    return [f"GO: {go['date']} commit {go['commit'][:12]}; source {go.get('source') or 'not recorded'}; "
            f"approved text {go.get('approved_text') or 'not recorded'}",
            f"ROUNDS: {go.get('rounds', 0)} extra per boundary from this go; {used}" + (f" ({go['rounds_lost']})" if go.get("rounds_lost") else "")]


def describe(budget: str, data: dict) -> str:
    cap = cap_in_force(data)
    settled, outstanding = totals(data)
    remaining = "none: no paid launches" if cap is None else f"{cap - settled - outstanding:.2f}"
    return f"BUDGET {budget}: cap {'none' if cap is None else f'{cap:.2f}'}, settled {settled:.2f}, outstanding {outstanding:.2f}, remaining {remaining}"


def named_before(project: Path, commit: str) -> Path | None:
    """A handoff of the project's checkouts whose Go field already names this go: its rounds may have been used."""
    checkouts = [project]
    try:
        listed = subprocess.run(["git", "-C", str(project), "worktree", "list", "--porcelain"], capture_output=True, text=True, timeout=10)
        checkouts += [Path(line[9:]) for line in listed.stdout.splitlines() if line.startswith("worktree ")]
    except (OSError, subprocess.SubprocessError):
        pass
    for checkout in checkouts:
        try:
            text = (checkout / ".dev-auto" / "handoff.md").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(line.startswith("- Go:") and f"commit {commit[:12]}" in line for line in text.splitlines()):
            return checkout / ".dev-auto" / "handoff.md"
    return None


def open_budget(args: dict) -> int:
    epic = args.get("--epic")
    if not (epic and epic.isdigit()):
        print("USAGE: open needs --epic N")
        return EXIT_USAGE
    epic = str(int(epic))  # 007 and 7 are one epic
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_needs
    project = Path(args.get("--project") or Path.cwd())
    needs = run_needs.run_needs(project, int(epic))
    budget = hashlib.sha256(plan_identity(needs["plan_root"]).encode()).hexdigest()[:16] + f"-epic-{epic}"
    with (ledger := Ledger(budget)) as data:
        data.setdefault("plan_root", needs["plan_root"])
        data.setdefault("epic", int(epic))
        data["project"] = str(project.resolve())  # where `round` reads the go again
        if "--cap" in args:
            cap = amount(args.get("--cap"))
            if cap is None or not args.get("--source"):
                print("REFUSED: an owner-stated cap needs a positive --cap and his words in --source")
                return EXIT_USAGE
            if needs["state"] == "GO" or data["gos"]:
                print("REFUSED: a cap is already set by his go or earlier; more money takes his new go")
                return EXIT_REFUSED
            data["gos"].append({"kind": "owner", "cap": cap, "source": args["--source"], "at": now()})
        elif needs["state"] == "GO":
            if not any(go.get("commit") == needs["go_commit"] for go in data["gos"]):
                latest = next((go for go in reversed(data["gos"]) if go.get("kind") == "go"), None)
                if latest and not go_follows(needs["plan_root"], latest["commit"], needs["go_commit"]):
                    print(f"REFUSED: go {needs['go_commit'][:12]} does not follow the recorded go {latest['commit'][:12]}; "
                          "read the plan's current history; the cap is unchanged")
                    return EXIT_REFUSED
                entry = {"kind": "go", "date": needs["go_date"], "commit": needs["go_commit"],
                         "cap": needs["parsed"]["money_cap"], "rounds": needs["parsed"]["rounds"],
                         "source": needs.get("approval_source"), "approved_text": needs.get("approved_text"),
                         "stories": needs.get("stories", []), "at": now()}
                # What was used under this go is not here to count when a run already began under it: count it all as used (D9).
                earlier = named_before(project, needs["go_commit"]) if entry["rounds"] else None
                started = needs.get("row_status") if entry["rounds"] and needs.get("row_status") not in (None, "ready") else None
                if earlier or started:
                    why = f"{earlier} names this go" if earlier else f"the epic's row is already {started}"
                    entry.update(rounds=0, rounds_lost=f"{why}, the ledger does not: its {needs['parsed']['rounds']} extra counted as used")
                data["gos"].append(entry)
            else:
                next(go for go in data["gos"] if go.get("commit") == needs["go_commit"]).setdefault("stories", needs.get("stories", []))
        elif go := latest_go(data):
            # The plan no longer gives the go in force: put back, or a later go that names no act (BMN 96 recheck).
            withdraw(data, go, needs.get("reason") or needs["state"])
        ledger.save()
        print(describe(budget, data))
        for line in describe_go(data):
            print(line)
    return 0


def take_round(args: dict) -> int:
    budget, boundary, use_id = args.get("--budget"), args.get("--boundary"), args.get("--use-id")
    if not (budget and boundary and use_id):
        print("USAGE: round needs --budget, --boundary STORY|epic and --use-id")
        return EXIT_USAGE
    if not BUDGET_ID.fullmatch(budget):
        raise ValueError(f"not a budget id: {budget}")
    match = BOUNDARY.fullmatch(boundary)
    if not match or (match.group(1) and match.group(1) != budget.rsplit("-", 1)[1]):
        print(f"USAGE: the boundary is one of epic {budget.rsplit('-', 1)[1]}'s stories (N.M) or `epic`, not {boundary}")
        return EXIT_USAGE
    with (ledger := Ledger(budget)) as data:
        earlier = data["rounds"].get(use_id)
        if earlier:
            print(f"{earlier['answer']}: round {use_id} was answered first at {earlier['at']} ({earlier['boundary']}); nothing taken again")
            return 0 if earlier["answer"] == "TAKEN" else EXIT_REFUSED
        go = latest_go(data)
        state, why = go_now(data, go) if go else ("stands", "")
        if state == "withdrawn":
            withdraw(data, go, why)
            ledger.save()
        if state != "stands":
            print(f"REFUSED: round {use_id} at {boundary}: the go {go['commit'][:12]} {'was withdrawn' if state == 'withdrawn' else 'cannot be confirmed'}: {why}; nothing taken")
            return EXIT_REFUSED
        if go and match.group(1) and boundary not in go.get("stories", []):
            print(f"USAGE: {boundary} is not one of the stories epic {data.get('epic')} had at its go ({', '.join(go.get('stories', [])) or 'none'}); nothing taken")
            return EXIT_USAGE
        allowed = go.get("rounds", 0) if go else 0
        used = rounds_used(data, boundary)
        answer = "TAKEN" if used < allowed else "REFUSED"
        data["rounds"][use_id] = {"answer": answer, "boundary": boundary, "go": go["commit"] if go else None, "at": now()}
        ledger.save()
        if answer == "REFUSED":
            reason = "no recorded go gives extra rounds" if go is None else f"the go gives {allowed} extra per boundary and {used} are used at {boundary}"
            print(f"REFUSED: round {use_id} at {boundary}: {reason}; nothing taken")
            return EXIT_REFUSED
        print(f"TAKEN: round {use_id} at {boundary}, {used + 1} of {allowed} from go {go['commit'][:12]}")
    return 0


def launch(args: dict, job_argv: list[str]) -> int:
    budget, job, maximum = args.get("--budget"), args.get("--job"), amount(args.get("--max"))
    if not (budget and job and job_argv):
        print("USAGE: launch needs --budget, --job and -- JOB_SCRIPT")
        return EXIT_USAGE
    if maximum is None:
        print("REFUSED: --max must be a positive amount in USD; nothing started")
        return EXIT_USAGE
    with (ledger := Ledger(budget)) as data:
        earlier = data["jobs"].get(job)
        if earlier:
            print(f"{earlier['answer']}: job {job} was answered first at {earlier['at']} ({earlier['state']}); nothing started again")
            return 0 if earlier["answer"] == "STARTED" else EXIT_REFUSED
        cap = cap_in_force(data)
        settled, outstanding = totals(data)
        if cap is None or settled + outstanding + maximum > cap + 1e-9:
            data["jobs"][job] = {"answer": "REFUSED", "state": "refused", "max": maximum, "at": now()}
            ledger.save()
            print(f"REFUSED: job {job} max {maximum:.2f} does not fit; {describe(budget, data)}; nothing started")
            return EXIT_REFUSED
        # The go the cap came from is read again, as a round reads it: one withdrawn or not confirmed starts nothing (BMN 96).
        go = latest_go(data)
        if go is not None and data["gos"][-1] is go:
            state, why = go_now(data, go)
            if state == "withdrawn":
                withdraw(data, go, why)
                ledger.save()
            if state != "stands":
                print(f"REFUSED: job {job}: the go {go['commit'][:12]} {'was withdrawn' if state == 'withdrawn' else 'cannot be confirmed'}: {why}; nothing started")
                return EXIT_REFUSED
        data["jobs"][job] = {"answer": "STARTED", "state": "reserved", "max": maximum, "at": now()}
        ledger.save()
        script = [str(Path(job_argv[0]).resolve()), *job_argv[1:]]
        try:
            if "--direct" in args:
                started = subprocess.Popen(["/bin/bash", *script], start_new_session=True,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                data["jobs"][job].update(state="started", pid=started.pid)
            else:
                done = subprocess.run(["systemd-run", "--user", "--collect", f"--setenv=PATH={os.environ.get('PATH', '')}",
                                       f"--property=WorkingDirectory={Path.cwd()}", "/bin/bash", *script],
                                      capture_output=True, text=True, timeout=60)
                if done.returncode != 0:
                    raise OSError(done.stderr.strip()[:200] or "systemd-run failed")
                unit = re.search(r"Running as unit: ([^\s;]+)", done.stderr + done.stdout)
                data["jobs"][job].update(state="started", unit=unit.group(1) if unit else None)
        except subprocess.TimeoutExpired as exc:
            # systemd may have accepted the job before its reply was lost: the outcome is unknown and keeps its money.
            data["jobs"][job].update(answer="UNKNOWN", state="unknown", error=str(exc)[:200])
            ledger.save()
            print(f"UNKNOWN: job {job} may have started ({exc}); its reservation is kept until it is settled or released")
            return EXIT_REFUSED
        except OSError as exc:
            data["jobs"][job].update(answer="NOT_STARTED", state="released", error=str(exc)[:200])
            ledger.save()
            print(f"NOT_STARTED: job {job} could not start ({exc}); its reservation is returned")
            return EXIT_REFUSED
        ledger.save()
        print(f"STARTED: job {job} reserved {maximum:.2f}; {describe(budget, data)}")
    return 0


def close(args: dict, verb: str) -> int:
    budget, job = args.get("--budget"), args.get("--job")
    with (ledger := Ledger(budget or "")) as data:
        entry = data["jobs"].get(job or "")
        if not entry or entry["answer"] not in ("STARTED", "UNKNOWN"):
            print(f"REFUSED: no started job {job} in budget {budget}")
            return EXIT_REFUSED
        if entry["state"] in ("settled", "released"):
            print(f"{entry['state'].upper()}: job {job} was closed at {entry.get('closed')}; nothing changed")
            return 0
        if verb == "release":
            entry.update(state="released", closed=now())
        elif "--unknown" in args:
            entry.update(state="unknown", closed=now())  # its reservation keeps counting
        else:
            try:
                spent = float(args.get("--spent") or "x")
            except ValueError:
                spent = -1.0
            if not math.isfinite(spent) or spent < 0:
                print("USAGE: settle needs --spent USD (0 or more) or --unknown")
                return EXIT_USAGE
            entry.update(state="settled", spent=spent, closed=now())
        ledger.save()
        print(f"{entry['state'].upper()}: job {job}; {describe(budget, data)}")
    return 0


def main(argv: list[str]) -> int:
    job_argv = argv[argv.index("--") + 1:] if "--" in argv else []
    argv = argv[:argv.index("--")] if "--" in argv else argv
    if not argv or {"-h", "--help"} & set(argv):
        print((__doc__ or "").strip())
        return 0 if argv else EXIT_USAGE
    args: dict = {}
    for index, word in enumerate(argv[1:], start=1):
        if word.startswith("--"):
            following = argv[index + 1] if index + 1 < len(argv) else None
            args[word] = following if following is not None and not following.startswith("--") else ""
    try:
        if argv[0] == "open":
            return open_budget(args)
        if argv[0] == "launch":
            return launch(args, job_argv)
        if argv[0] in ("settle", "release"):
            return close(args, argv[0])
        if argv[0] == "round":
            return take_round(args)
        if argv[0] == "status":
            with Ledger(args.get("--budget") or "") as data:
                print(describe(args["--budget"], data))
                for line in describe_go(data):
                    print(line)
                for job, entry in data["jobs"].items():
                    print(f"  {job}: {entry['state']} max {entry['max']:.2f}" + (f" spent {entry['spent']:.2f}" if "spent" in entry else ""))
            return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"UNABLE: {exc}")
        return EXIT_USAGE
    print((__doc__ or "").strip())
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
