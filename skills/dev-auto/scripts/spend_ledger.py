#!/usr/bin/env python3
# MODULE: spend_ledger.py - BMN Epic 90.4: the go's money cap kept at every paid launch by one reservation ledger per plan and epic
"""Reserve a paid job's maximum against the epic's money cap before it starts.

Usage:
  spend_ledger.py open --epic N [--project P]             record the epic's go and its cap; prints the budget id
  spend_ledger.py open --epic N --cap USD --source TEXT   an owner-stated cap for an epic with no go and no cap yet
  spend_ledger.py launch --budget B --job J --max USD [--direct] -- JOB_SCRIPT [ARGS...]
  spend_ledger.py settle --budget B --job J (--spent USD | --unknown)
  spend_ledger.py release --budget B --job J              the job never ran: its reservation is returned
  spend_ledger.py status --budget B

One ledger per plan root and epic, under $XDG_STATE_HOME/dev-auto/budgets/ (default ~/.local/state), outside every
worktree, shared by resumes, new leads and replacement runs. The cap in force is the latest go's; `none` refuses
every paid launch. A reapproval never resets what was settled or reserved: it counts against the new cap. `launch`
reserves only when settled + outstanding reservations + this maximum stay within the cap, writing atomically under
a lock, then starts the job detached (`systemd-run --user`, as references/models.md runs paid jobs; `--direct`
starts it as a detached process instead). A refusal, an invalid amount or a missing maximum starts nothing and exits
non-zero; a retry under the same job id returns the first answer. An unknown outcome keeps its reservation. The
ledger covers dev-auto's own paid launches, not every provider call.
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


def cap_in_force(data: dict) -> float | None:
    return data["gos"][-1]["cap"] if data["gos"] else None


def totals(data: dict) -> tuple[float, float]:
    jobs = data["jobs"].values()
    settled = sum(job.get("spent", 0.0) for job in jobs if job["state"] == "settled")
    outstanding = sum(job["max"] for job in jobs if job["state"] in ("reserved", "started", "unknown"))
    return settled, outstanding


def describe(budget: str, data: dict) -> str:
    cap = cap_in_force(data)
    settled, outstanding = totals(data)
    remaining = "none: no paid launches" if cap is None else f"{cap - settled - outstanding:.2f}"
    return f"BUDGET {budget}: cap {'none' if cap is None else f'{cap:.2f}'}, settled {settled:.2f}, outstanding {outstanding:.2f}, remaining {remaining}"


def open_budget(args: dict) -> int:
    epic = args.get("--epic")
    if not (epic and epic.isdigit()):
        print("USAGE: open needs --epic N")
        return EXIT_USAGE
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_needs
    needs = run_needs.run_needs(Path(args.get("--project") or Path.cwd()), int(epic))
    budget = hashlib.sha256(needs["plan_root"].encode()).hexdigest()[:16] + f"-epic-{epic}"
    with (ledger := Ledger(budget)) as data:
        data.setdefault("plan_root", needs["plan_root"])
        data.setdefault("epic", int(epic))
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
                data["gos"].append({"kind": "go", "date": needs["go_date"], "commit": needs["go_commit"],
                                    "cap": needs["parsed"]["money_cap"], "at": now()})
        ledger.save()
        print(describe(budget, data))
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
                unit = re.search(r"Running as unit: (\S+)", done.stderr + done.stdout)
                data["jobs"][job].update(state="started", unit=unit.group(1) if unit else None)
        except (OSError, subprocess.TimeoutExpired) as exc:
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
        if not entry or entry["answer"] != "STARTED":
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
        if argv[0] == "status":
            with Ledger(args.get("--budget") or "") as data:
                print(describe(args["--budget"], data))
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
