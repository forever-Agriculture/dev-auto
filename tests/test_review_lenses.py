# MODULE: test_review_lenses.py - BMN Epic 105.3: the lens runner against a fake bmn: Busy, exhaustion, refusal, bad answers, hung and dead calls, own asks only
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "dev-auto" / "scripts" / "review_lenses.py"
FAKE_BMN = """#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
plan = json.load(open(os.environ["FAKE_PLAN"]))
counts_path = os.environ["FAKE_LOG"] + ".counts"
counts = json.load(open(counts_path)) if os.path.exists(counts_path) else {}
def bump(name):
    counts[name] = counts.get(name, 0) + 1
    json.dump(counts, open(counts_path, "w"))
    return counts[name]
if args[:2] == ["team", "ask"]:
    lens = args[args.index("--key") + 1].rsplit("-review-", 1)[1].split("-", 1)[1]
    seen = bump("ask-" + lens)
    entry = plan.get(lens, {})
    if entry.get("hang"):
        time.sleep(60)
    if seen <= entry.get("busy", 0):
        print(json.dumps({"state": "refused", "exit": 14, "refusal": {"code": "BUSY", "reason": "4 asks are running"}}))
        sys.exit(14)
    if entry.get("refuse"):
        print(json.dumps({"state": "refused", "exit": 10, "refusal": {"code": "NO", "reason": entry["refuse"]}}))
        sys.exit(10)
    print(json.dumps({"id": "run-" + lens, "state": "accepted", "exit": 0}))
elif args[:3] == ["team", "asks", "show"]:
    lens = args[3].split("-", 1)[1]
    seen = bump("show-" + lens)
    entry = plan.get(lens, {})
    if seen <= entry.get("running", 0):
        print(json.dumps({"id": args[3], "state": "running"}))
    elif entry.get("ended"):
        print(json.dumps({"id": args[3], "state": entry["ended"], "exit": 1}))
    else:
        answer = entry.get("answer", json.dumps({"lens": lens, "findings": []}))
        print(json.dumps({"id": args[3], "state": "answered", "exit": 0, "answer": answer}))
elif args[:3] == ["team", "asks", "stop"]:
    print(json.dumps({"id": args[3], "state": "stopped", "exit": 0}))
else:
    sys.exit(9)
"""


class Run(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        (self.root / "bin").mkdir()
        bmn = self.root / "bin" / "bmn"
        bmn.write_text(FAKE_BMN)
        bmn.chmod(bmn.stat().st_mode | stat.S_IEXEC)
        self.skill = self.root / "skill"
        (self.skill / "references" / "lenses").mkdir(parents=True)
        (self.skill / "references" / "rules.md").write_text("rules")
        for lens in ("bugs", "architect", "one-of-each", "platform"):
            (self.skill / "references" / "lenses" / f"{lens}.md").write_text(lens)
        self.pack = self.root / "pack" / "pack.md"
        self.pack.parent.mkdir()
        self.pack.write_text("pack")
        (self.root / "lessons.md").write_text("lessons")
        (self.root / "project").mkdir()
        self.log = self.root / "log"

    def run_it(self, plan: dict, lenses: list[str], *extra: str) -> subprocess.CompletedProcess[str]:
        (self.pack.parent / "pack.json").write_text(json.dumps({"repos": [], "lenses": lenses}))
        (self.root / "plan.json").write_text(json.dumps(plan))
        env = {**os.environ, "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}", "FAKE_LOG": str(self.log), "FAKE_PLAN": str(self.root / "plan.json")}
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--pack", str(self.pack), "--skill", str(self.skill), "--project", str(self.root / "project"),
             "--lessons", str(self.root / "lessons.md"), "--retry-seconds", "0.05", "--poll-seconds", "0.05", *extra],
            capture_output=True, text=True, env=env, timeout=60,
        )

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_every_lens_the_pack_lists_goes_on_its_route_and_is_written(self) -> None:
        done = self.run_it({}, ["one-of-each", "bugs", "platform", "architect"])
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("ANSWERED 4 of 4", done.stdout)
        asks = {c[c.index("--key") + 1].rsplit("-", 1)[-1]: c for c in self.calls() if c[:2] == ["team", "ask"]}
        self.assertEqual(len(asks), 4)
        routes = {}
        for call in self.calls():
            if call[:2] == ["team", "ask"]:
                routes[call[call.index("--key") + 1].split("-review-")[1].split("-", 1)[1]] = (call[call.index("--agent") + 1], call[call.index("--effort") + 1])
        self.assertEqual(routes, {"bugs": ("astra", "medium"), "architect": ("astra", "medium"), "one-of-each": ("luna", "max"), "platform": ("luna", "max")})
        for lens in routes:
            self.assertEqual(json.loads((self.pack.parent / "lenses" / f"{lens}.json").read_text())["lens"], lens)

    def test_busy_then_success_keeps_the_same_key(self) -> None:
        done = self.run_it({"bugs": {"busy": 3}}, ["bugs"])
        self.assertEqual(done.returncode, 0, done.stdout)
        keys = {c[c.index("--key") + 1] for c in self.calls() if c[:2] == ["team", "ask"]}
        self.assertEqual(len(keys), 1)
        self.assertEqual(sum(c[:2] == ["team", "ask"] for c in self.calls()), 4)

    def test_busy_past_its_limit_is_blocked(self) -> None:
        done = self.run_it({"bugs": {"busy": 10000}}, ["bugs"], "--busy-seconds", "0.3")
        self.assertEqual(done.returncode, 1)
        self.assertIn("BLOCKED: bugs: busy past the limit", done.stdout)
        self.assertFalse(any(c[:3] == ["team", "asks", "stop"] for c in self.calls()))

    def test_a_refusal_is_blocked_at_once_with_its_reason(self) -> None:
        done = self.run_it({"bugs": {"refuse": "not eligible"}}, ["bugs"])
        self.assertEqual(done.returncode, 1)
        self.assertIn("not eligible", done.stdout)
        self.assertEqual(sum(c[:2] == ["team", "ask"] for c in self.calls()), 1)

    def test_a_malformed_answer_is_no_answer(self) -> None:
        for answer in ("I found nothing.", json.dumps({"lens": "other", "findings": []}), json.dumps({"lens": "bugs"}), ""):
            with self.subTest(answer=answer):
                if self.log.exists():
                    self.log.unlink()
                    Path(str(self.log) + ".counts").unlink()
                done = self.run_it({"bugs": {"answer": answer}}, ["bugs"])
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn("not the object", done.stdout)
                self.assertFalse((self.pack.parent / "lenses" / "bugs.json").exists())

    def test_a_fenced_answer_counts(self) -> None:
        done = self.run_it({"bugs": {"answer": "```json\n" + json.dumps({"lens": "bugs", "findings": [{"title": "x"}]}) + "\n```"}}, ["bugs"])
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("1 findings", done.stdout)

    def test_a_run_that_ended_without_an_answer_is_blocked(self) -> None:
        done = self.run_it({"bugs": {"ended": "failed"}}, ["bugs"])
        self.assertEqual(done.returncode, 1)
        self.assertIn("the ask ended failed", done.stdout)

    def test_a_running_ask_past_the_deadline_is_stopped_and_only_that_one(self) -> None:
        done = self.run_it({"bugs": {"running": 100000}, "platform": {}}, ["bugs", "platform"], "--seconds", "0.6")
        self.assertEqual(done.returncode, 1)
        self.assertIn("BLOCKED: bugs: no answer by the deadline", done.stdout)
        stops = [c[3] for c in self.calls() if c[:3] == ["team", "asks", "stop"]]
        self.assertEqual(stops, ["run-bugs"])

    def test_a_hung_call_cannot_outlive_its_deadline(self) -> None:
        source = SCRIPT.read_text()
        self.assertIn("timeout=CALL_SECONDS", source)
        hung = self.root / "short.py"
        hung.write_text(source.replace("CALL_SECONDS = 60", "CALL_SECONDS = 0.3"))
        (self.pack.parent / "pack.json").write_text(json.dumps({"lenses": ["bugs"]}))
        (self.root / "plan.json").write_text(json.dumps({"bugs": {"hang": True}}))
        env = {**os.environ, "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}", "FAKE_LOG": str(self.log), "FAKE_PLAN": str(self.root / "plan.json")}
        began = time.monotonic()
        done = subprocess.run([sys.executable, str(hung), "--pack", str(self.pack), "--skill", str(self.skill), "--project", str(self.root / "project"),
                               "--lessons", str(self.root / "lessons.md"), "--busy-seconds", "0.5", "--seconds", "2", "--retry-seconds", "0.05"],
                              capture_output=True, text=True, env=env, timeout=30)
        self.assertLess(time.monotonic() - began, 15)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("did not answer", done.stdout)

    def test_a_missing_lens_route_or_file_or_bmn_is_blocked_not_guessed(self) -> None:
        done = self.run_it({}, ["design"])
        self.assertEqual(done.returncode, 1)
        self.assertIn("no route for design", done.stdout)
        (self.skill / "references" / "lenses" / "bugs.md").unlink()
        done = self.run_it({}, ["bugs"])
        self.assertEqual(done.returncode, 1)
        self.assertIn("missing", done.stdout)

    def test_a_usage_error_is_exit_two(self) -> None:
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "--pack"], capture_output=True, text=True).returncode, 2)
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
