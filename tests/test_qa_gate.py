# MODULE: test_qa_gate.py - native-record binding and retest failures stay blocking for either lead app
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/dev-auto/scripts/qa_gate.py"


class QaGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # Contract seam only: the real BMN checker is exercised against a live QA export separately.
        self.checker = self.root / "bmn-checker"
        self.checker.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
        self.checker.chmod(0o755)

    def write(self, root, name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def write_qa(self, root, name, value):
        """A genuine quick export: BMN wrote qa/ from its input manifest and the retained native answer."""
        self.write(root, name, value)
        brief, report = self.load(root, "qa/brief.json"), self.load(root, "qa/report.json")
        self.write(root, "inputs/manifest.json", {"id": root.name, "qa": {"brief": brief}, "browser": {"origin": brief["target"]}})
        (root / "answer.md").write_text(json.dumps(report, indent=2) + "\n")

    def record(self, name="current", revision="candidate-2", verdict="GO", finding=None):
        root = self.root / name
        brief = {"revision": revision, "target": "http://127.0.0.1:4173", "prior_findings": []}
        report = {"verdict": verdict, "goal_check": {"status": "achieved", "execution": "started"},
                  "criteria": [{"id": "AC1", "evidence": ["browser/cart.png"]}],
                  "findings": [] if finding is None else [finding]}
        self.write(root, "qa/brief.json", brief)
        self.write_qa(root, "qa/report.json", report)
        self.write(root, "request.json", {"id": name, "role": "qa", "browser": {"origin": brief["target"]}})
        self.write(root, "outcome.json", {"id": name, "state": "answered", "qa": {"valid": True, "verdict": verdict,
                   "brief": "qa/brief.json", "report": "qa/report.json"}})
        image = root / "browser/cart.png"
        image.parent.mkdir(); image.write_bytes(b"synthetic-native-image-fixture")
        self.write(root, "browser.json", {"origin": brief["target"], "calls": 3, "screenshots": [{"name": "cart.png", "bytes": image.stat().st_size,
                   "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}]})
        return root

    def invoke(self, record, revision="candidate-2", target="http://127.0.0.1:4173", *extra):
        result = subprocess.run([sys.executable, str(SCRIPT), str(record), "--revision", revision, "--target", target,
                                 "--bmn", str(self.checker), *map(str, extra)], text=True, capture_output=True, timeout=30)
        return result.returncode, json.loads(result.stdout)

    def load(self, root, name):
        return json.loads((root / name).read_text())

    def finding(self, resolved=False, retest=False):
        finding = {"id": "F1", "severity": "major", "status": "resolved" if resolved else "open", "actual": "Selection disappears", "evidence": []}
        if retest:
            finding["retest"] = {"steps": ["Repeat the selection"], "observations": "Selection observed", "regression_gaps": []}
        return finding

    def retest(self, same_revision=False, resolved=True, observed=True):
        original = self.finding()
        prior = self.record("prior", "candidate-1", "NO-GO", original)
        current = self.record(revision="candidate-1" if same_revision else "candidate-2", verdict="GO" if resolved else "NO-GO",
                              finding=self.finding(resolved, observed))
        brief = self.load(current, "qa/brief.json")
        brief["prior_findings"] = [{"finding": original, "disposition": "Repaired selection; QA must verify"}]
        self.write_qa(current, "qa/brief.json", brief)
        return prior, current

    def test_bound_go_passes_identically_on_resume_without_writing(self):
        record = self.record()
        before = {str(path): path.read_bytes() for path in record.rglob("*") if path.is_file()}
        for _ in range(2):
            code, result = self.invoke(record)
            self.assertEqual((code, result["status"], result["verdict"]), (0, "pass", "GO"))
        self.assertEqual(before, {str(path): path.read_bytes() for path in record.rglob("*") if path.is_file()})

    def test_no_go_remains_blocked_even_when_the_shared_checker_succeeded(self):
        code, result = self.invoke(self.record(verdict="NO-GO"))
        self.assertEqual((code, result["status"], result["verdict"]), (1, "blocked", "NO-GO"))

    def test_another_candidate_or_target_never_passes(self):
        record = self.record()
        for revision, target in [("other", "http://127.0.0.1:4173"), ("candidate-2", "http://127.0.0.1:4174")]:
            with self.subTest(revision=revision, target=target):
                self.assertEqual(self.invoke(record, revision, target)[1]["status"], "invalid")

    def test_relabelled_quick_export_never_passes(self):
        # Astra's reproduction: qa/ rewritten consistently for an untested candidate while BMN's native record is unchanged.
        for change in ["candidate", "criteria", "report", "answer", "browser"]:
            with self.subTest(change=change):
                root = self.record(name=change)
                brief, report, revision, target = self.load(root, "qa/brief.json"), self.load(root, "qa/report.json"), "candidate-2", "http://127.0.0.1:4173"
                if change == "candidate":
                    revision, target = "never-tested-candidate", "http://127.0.0.1:49999"
                    brief.update(revision=revision, target=target)
                    browser = self.load(root, "browser.json"); browser["origin"] = target; self.write(root, "browser.json", browser)
                elif change == "criteria": brief["criteria"] = [{"id": "AC1", "description": "Something easier", "mandatory": True}]
                elif change == "report": report["goal_check"]["status"] = "uncertain"
                elif change == "answer": (root / "answer.md").write_text("not the report")
                elif change == "browser":
                    browser = self.load(root, "browser.json"); browser["origin"] = "http://127.0.0.1:49999"; self.write(root, "browser.json", browser)
                self.write(root, "qa/brief.json", brief); self.write(root, "qa/report.json", report)
                self.assertEqual(self.invoke(root, revision, target)[1]["status"], "invalid")
        root = self.record(name="moved-request")
        request = self.load(root, "request.json"); request["browser"]["origin"] = "http://127.0.0.1:49999"; self.write(root, "request.json", request)
        self.assertIn("browser request", self.invoke(root)[1]["reason"])

    def test_missing_and_unavailable_qa_records_never_pass(self):
        record = self.record()
        self.write(record, "outcome.json", {"id": "current", "state": "failed", "qa": None})
        self.assertEqual(self.invoke(record)[1]["status"], "invalid")
        (record / "qa/report.json").unlink()
        self.assertEqual(self.invoke(record)[0], 1)

    def test_native_invalid_and_verdict_mismatch_never_pass(self):
        for valid, verdict in [(False, "GO"), (True, "NO-GO")]:
            record = self.record(str(valid) + verdict)
            outcome = self.load(record, "outcome.json"); outcome["qa"].update(valid=valid, verdict=verdict)
            self.write(record, "outcome.json", outcome)
            self.assertEqual(self.invoke(record)[1]["status"], "invalid")

    def test_screenshot_must_match_the_retained_native_hash(self):
        record = self.record(); (record / "browser/cart.png").write_bytes(b"different bytes")
        self.assertIn("native hash", self.invoke(record)[1]["reason"])

    def test_shared_checker_failure_cannot_be_overridden_by_native_valid_flag(self):
        self.checker.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n")
        self.assertIn("shared report checker", self.invoke(self.record())[1]["reason"])

    def test_an_open_finding_does_not_prove_a_retest(self):
        prior, current = self.retest(resolved=False, observed=False)
        self.assertIn("no current original-repro retest", self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--prior", prior)[1]["reason"])

    def test_observed_but_still_failing_retest_keeps_product_no_go(self):
        prior, current = self.retest(resolved=False)
        code, result = self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--prior", prior)
        self.assertEqual((code, result["status"], result["verdict"]), (1, "blocked", "NO-GO"))

    def test_a_repaired_revision_with_original_repro_retest_can_pass(self):
        prior, current = self.retest()
        self.assertEqual(self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--prior", prior)[0], 0)

    def test_unchanged_candidate_cannot_close_an_intermittent_defect(self):
        prior, current = self.retest(same_revision=True)
        self.assertIn("unchanged candidate", self.invoke(current, "candidate-1", "http://127.0.0.1:4173", "--prior", prior)[1]["reason"])

    def test_prior_finding_facts_cannot_be_downgraded_in_the_recheck_brief(self):
        prior, current = self.retest()
        brief = self.load(current, "qa/brief.json"); brief["prior_findings"][0]["finding"]["severity"] = "minor"
        self.write_qa(current, "qa/brief.json", brief)
        self.assertIn("facts are missing or changed", self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--prior", prior)[1]["reason"])

    def minor_retest(self, same_revision=False, resolved=True, observed=True):
        prior, current = self.retest(same_revision, resolved, observed)
        old = self.load(prior, "qa/report.json"); old["findings"][0]["severity"] = "minor"
        old["verdict"] = "GO WITH ISSUES"; self.write_qa(prior, "qa/report.json", old)
        outcome = self.load(prior, "outcome.json"); outcome["qa"]["verdict"] = old["verdict"]
        self.write(prior, "outcome.json", outcome)
        new = self.load(current, "qa/report.json"); new["findings"][0]["severity"] = "minor"
        new["verdict"] = "GO" if resolved else "GO WITH ISSUES"; self.write_qa(current, "qa/report.json", new)
        outcome = self.load(current, "outcome.json"); outcome["qa"]["verdict"] = new["verdict"]
        self.write(current, "outcome.json", outcome)
        brief = self.load(current, "qa/brief.json"); brief["prior_findings"][0]["finding"] = old["findings"][0]
        self.write_qa(current, "qa/brief.json", brief)
        return prior, current

    def test_open_minor_still_needs_current_repro_observations(self):
        prior, current = self.minor_retest(resolved=False, observed=False)
        self.assertEqual(self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--prior", prior)[1]["status"], "invalid")
        self.assertIn("no current original-repro retest", self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--prior", prior)[1]["reason"])

    def test_minor_cannot_be_closed_on_the_unchanged_candidate(self):
        prior, current = self.minor_retest(same_revision=True)
        self.assertEqual(self.invoke(current, "candidate-1", "http://127.0.0.1:4173", "--prior", prior)[1]["status"], "invalid")
        self.assertIn("unchanged candidate", self.invoke(current, "candidate-1", "http://127.0.0.1:4173", "--prior", prior)[1]["reason"])

    def test_prior_minor_cannot_silently_disappear_from_the_recheck(self):
        prior, current = self.minor_retest()
        report = self.load(current, "qa/report.json"); report["findings"] = []
        self.write_qa(current, "qa/report.json", report)
        self.assertEqual(self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--prior", prior)[1]["status"], "invalid")
        self.assertIn("no current original-repro retest", self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--prior", prior)[1]["reason"])

    def test_minor_observed_still_open_on_same_revision_is_not_a_fix_claim(self):
        prior, current = self.minor_retest(same_revision=True, resolved=False)
        self.assertEqual(self.invoke(current, "candidate-1", "http://127.0.0.1:4173", "--prior", prior)[1]["status"], "pass")

    def test_retest_needs_the_earlier_admitted_record(self):
        self.assertIn("requires the earlier", self.invoke(self.record(), "candidate-2", "http://127.0.0.1:4173", "--retest", "F1")[1]["reason"])


    # History: an earlier admitted resolution, a prior on the same label that reopened it only for missing coverage,
    # an independent native review declaring no recurrence, and a full new reproduction.
    STEPS = ["Open the cart", "Repeat the selection"]

    def history_chain(self, name="", current_verdict="GO"):
        base = {"id": "F1", "severity": "major", "steps": self.STEPS, "actual": "Selection disappears", "evidence": []}
        resolved = dict(base, status="resolved", evidence=["browser/cart.png"],
                        retest={"steps": self.STEPS, "observations": "Selection kept", "regression_gaps": []})
        history = self.record("history" + name, "candidate-1", "GO", resolved)
        reopened = dict(base, status="open")
        prior = self.record("prior" + name, "candidate-2", "NO-GO", reopened)
        brief = self.load(prior, "qa/brief.json")
        brief["prior_findings"] = [{"finding": dict(resolved, evidence=[]), "disposition": "Resolved earlier"}]
        self.write_qa(prior, "qa/brief.json", brief)
        closed = dict(base, status="resolved", evidence=["browser/cart.png"],
                      retest={"steps": self.STEPS, "observations": "Selection kept on the full reproduction", "regression_gaps": []})
        current = self.record("current" + name, "candidate-2", current_verdict, closed)
        brief = self.load(current, "qa/brief.json")
        brief["prior_findings"] = [{"finding": reopened, "disposition": "Reopened untested; full reproduction assigned"}]
        brief["criteria"] = [{"id": "retest:F1", "description": "Full original reproduction: " + "; ".join(self.STEPS), "mandatory": True}]
        self.write_qa(current, "qa/brief.json", brief)
        report = self.load(current, "qa/report.json")
        report["criteria"] = [{"id": "retest:F1", "status": "PASS", "evidence": ["browser/cart.png"]}]
        self.write_qa(current, "qa/report.json", report)
        return history, prior, current

    def binding(self, history, prior, revision="candidate-2", target="http://127.0.0.1:4173"):
        digest = lambda root: hashlib.sha256((root / "qa/report.json").read_bytes()).hexdigest()
        return f"HISTORY REVIEW: history-report {digest(history)}; prior-report {digest(prior)}; revision {revision}; target {target}"

    def review(self, history, prior, name="review", lines=None, role="epic-reviewer", claude=False):
        root = self.root / name
        text = "\n".join([self.binding(history, prior), "F1: NO RECURRENCE"] if lines is None else lines) + "\n\nRESULT: done"
        self.write(root, "request.json", {"id": name, "role": role})
        self.write(root, "outcome.json", {"id": name, "state": "answered"})
        self.write(root, "inputs/manifest.json", {"id": name})
        event = ({"type": "result", "result": text} if claude
                 else {"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": text}})
        (root / "events.jsonl").write_text(json.dumps({"type": "thread.started"}) + "\n" + json.dumps(event) + "\n")
        (root / "answer.md").write_text(text + "\n")
        return root

    def gate(self, history, prior, current, review, *extra, revision="candidate-2"):
        return self.invoke(current, revision, "http://127.0.0.1:4173", "--prior", prior, "--history", history,
                           "--history-review", review, *extra)

    def test_history_closes_a_coverage_reopen_on_the_same_candidate(self):
        cases = [(role, claude) for role in ["epic-reviewer", "small-epic-reviewer"] for claude in [False, True]]
        for role, claude in cases:
            with self.subTest(role=role, claude=claude):
                history, prior, current = self.history_chain(f"-{role}-{claude}")
                review = self.review(history, prior, f"review-{role}-{claude}", role=role, claude=claude)
                before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
                code, result = self.gate(history, prior, current, review)
                self.assertEqual((code, result["status"], result.get("history_closures")), (0, "pass", ["F1"]))
                self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_history_closure_keeps_a_no_go_blocked(self):
        history, prior, current = self.history_chain(current_verdict="NO-GO")
        code, result = self.gate(history, prior, current, self.review(history, prior))
        self.assertEqual((code, result["status"], result.get("history_closures")), (1, "blocked", ["F1"]))

    def test_same_label_without_history_still_cannot_close(self):
        history, prior, current = self.history_chain()
        self.assertIn("unchanged candidate", self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--prior", prior)[1]["reason"])

    def test_history_arguments_never_stand_alone_or_widen_a_repair_claim(self):
        history, prior, current = self.history_chain()
        review = self.review(history, prior)
        target = "http://127.0.0.1:4173"
        self.assertIn("--retest", self.gate(history, prior, current, review, "--retest", "F1")[1]["reason"])
        self.assertIn("needs --history-review", self.invoke(current, "candidate-2", target, "--prior", prior, "--history", history)[1]["reason"])
        self.assertIn("needs --history-review", self.invoke(current, "candidate-2", target, "--prior", prior, "--history-review", review)[1]["reason"])
        self.assertIn("require --prior", self.invoke(current, "candidate-2", target, "--history", history, "--history-review", review)[1]["reason"])

    def test_history_refuses_a_different_label(self):
        history, prior, current = self.history_chain()
        brief = self.load(current, "qa/brief.json"); brief["revision"] = "candidate-3"; self.write_qa(current, "qa/brief.json", brief)
        review = self.review(history, prior)
        self.assertIn("own candidate label", self.gate(history, prior, current, review, revision="candidate-3")[1]["reason"])

    def test_history_review_must_be_an_independent_bound_native_answer(self):
        cases = {"no-binding": (["F1: NO RECURRENCE"], {}), "uncertain": (None, {"line": "F1: UNCERTAIN"}),
                 "missing-id": (None, {"line": None}), "duplicate": (None, {"extra": "F1: recurred in another section"}),
                 "stale": (None, {"stale": True}), "target": (None, {"target": "http://127.0.0.1:4174"}),
                 "revision": (None, {"revision": "candidate-1"}), "role": (None, {"role": "qa"}),
                 "substituted": (None, {"substitute": True}), "unanswered": (None, {"unanswered": True})}
        for name, (lines, change) in cases.items():
            with self.subTest(case=name):
                history, prior, current = self.history_chain("-" + name)
                binding = self.binding(history, prior, change.get("revision", "candidate-2"), change.get("target", "http://127.0.0.1:4173"))
                if change.get("stale"): binding = binding.replace("prior-report ", "prior-report 0")
                if lines is None:
                    lines = [binding] + ([change["line"]] if "line" in change and change["line"] else [] if "line" in change else ["F1: NO RECURRENCE"])
                    if "extra" in change: lines.append(change["extra"])
                review = self.review(history, prior, "review-" + name, lines, change.get("role", "epic-reviewer"))
                if change.get("substitute"): (review / "answer.md").write_text("\n".join([binding, "F1: NO RECURRENCE"]) + "\n")
                if change.get("unanswered"): self.write(review, "outcome.json", {"id": "review-" + name, "state": "failed"})
                self.assertEqual(self.gate(history, prior, current, review)[1]["status"], "invalid")

    def mutate(self, history, prior, current, change):
        hr, pb, pr = self.load(history, "qa/report.json"), self.load(prior, "qa/brief.json"), self.load(prior, "qa/report.json")
        cb, cr = self.load(current, "qa/brief.json"), self.load(current, "qa/report.json")
        if change == "prior-linked": pr["criteria"] = [{"id": "AC1", "status": "FAIL", "evidence": ["browser/cart.png"], "finding_ids": ["F1"]}]
        elif change == "prior-evidence":
            pr["findings"][0]["evidence"] = ["browser/cart.png"]; cb["prior_findings"][0]["finding"] = pr["findings"][0]
        elif change == "prior-actual":
            for finding in [pr["findings"][0], cb["prior_findings"][0]["finding"], cr["findings"][0]]: finding["actual"] = "Selection flickers"
        elif change == "prior-new": pb["prior_findings"] = []
        elif change == "handed-severity": pb["prior_findings"][0]["finding"]["severity"] = "minor"
        elif change == "history-open": hr["findings"][0]["status"] = "open"
        elif change == "history-no-steps": hr["findings"][0]["retest"]["steps"] = []
        elif change == "history-no-observations": hr["findings"][0]["retest"]["observations"] = " "
        elif change == "criterion-missing": cb["criteria"] = []
        elif change == "criterion-optional": cb["criteria"][0]["mandatory"] = False
        elif change == "criterion-partial": cb["criteria"][0]["description"] = "Full original reproduction: " + self.STEPS[1]
        elif change == "criterion-blocked": cr["criteria"][0]["status"] = "BLOCKED"
        elif change == "criterion-no-evidence": cr["criteria"][0]["evidence"] = []
        elif change == "current-severity": cr["findings"][0]["severity"] = "minor"
        for root, name, value in [(history, "qa/report.json", hr), (prior, "qa/brief.json", pb), (prior, "qa/report.json", pr),
                                  (current, "qa/brief.json", cb), (current, "qa/report.json", cr)]:
            self.write_qa(root, name, value)

    def test_history_mutations_never_close(self):
        reasons = {"prior-linked": "coverage reopen", "prior-evidence": "coverage reopen", "prior-actual": "coverage reopen",
                   "prior-new": "hand over", "handed-severity": "hand over", "history-open": "retested resolution",
                   "history-no-steps": "retested resolution", "history-no-observations": "retested resolution",
                   "criterion-missing": "retest:F1", "criterion-optional": "retest:F1", "criterion-partial": "retest:F1",
                   "criterion-blocked": "retest:F1", "criterion-no-evidence": "retest:F1",
                   "current-severity": "current finding facts", "history-answer": ""}
        for change, reason in reasons.items():
            with self.subTest(change=change):
                history, prior, current = self.history_chain("-" + change)
                if change == "history-answer": (history / "answer.md").write_text("not the report")
                else: self.mutate(history, prior, current, change)
                result = self.gate(history, prior, current, self.review(history, prior, "review-" + change))[1]
                self.assertEqual(result["status"], "invalid")
                self.assertIn(reason, result["reason"])


    def session_record(self, verdict="GO", name="current"):
        return self.as_session_record(self.record(name=name, verdict=verdict))

    def as_session_record(self, root):
        brief = self.load(root, "qa/brief.json"); brief["mode"] = "session"
        self.write(root, "qa/brief.json", brief)
        report = self.load(root, "qa/report.json")
        connection = {"pid": 102, "ticks": "600", "at": "2026-10-29T00:00:00Z"}
        run = {"id": "qa-current", "state": "finished", "folder": str(root), "sessionId": "pane", "incarnationId": "run-1",
               "brief": brief, "inputSha256": hashlib.sha256(json.dumps(brief, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
               "agent": {"pid": 101, "ticks": "599"}, "connection": connection,
               "result": {"valid": True, "verdict": report["verdict"], "errors": [], "report": report}}
        browser = self.load(root, "browser.json"); browser.update(qaId=run["id"], connection={"pid": 102, "ticks": "600"})
        self.write(root, "browser.json", browser)
        self.write(root, "session-run.json", run)
        for name in ["request.json", "outcome.json"]:
            (root / name).unlink()
        return root

    def test_native_session_report_uses_the_same_gate_and_resumes_without_writes(self):
        root = self.session_record()
        before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        for _ in range(2):
            code, result = self.invoke(root, "candidate-2", "http://127.0.0.1:4173", "--session-run", root / "session-run.json")
            self.assertEqual((code, result["status"]), (0, "pass"))
        self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_native_session_no_go_keeps_its_product_verdict(self):
        root = self.session_record("NO-GO")
        code, result = self.invoke(root, "candidate-2", "http://127.0.0.1:4173", "--session-run", root / "session-run.json")
        self.assertEqual((code, result["status"], result["verdict"]), (1, "blocked", "NO-GO"))

    def test_native_session_failed_retest_preserves_original_findings_and_no_go(self):
        prior, current = self.retest(resolved=False)
        self.as_session_record(prior); self.as_session_record(current)
        code, result = self.invoke(current, "candidate-2", "http://127.0.0.1:4173", "--session-run", current / "session-run.json",
                                   "--prior", prior, "--prior-session-run", prior / "session-run.json", "--retest", "F1")
        self.assertEqual((code, result["status"], result["verdict"]), (1, "blocked", "NO-GO"))

    def test_session_cannot_borrow_another_runs_browser_or_report(self):
        for mismatch in ["qaId", "connection", "report", "folder", "brief", "agent", "failed"]:
            with self.subTest(mismatch=mismatch):
                root = self.session_record(name=mismatch)
                run = self.load(root, "session-run.json")
                browser = self.load(root, "browser.json")
                if mismatch == "qaId": browser["qaId"] = "another-qa"
                elif mismatch == "connection": browser["connection"]["ticks"] = "other-incarnation"
                elif mismatch == "report": run["result"]["report"]["verdict"] = "NO-GO"
                elif mismatch == "folder": run["folder"] = str(self.root / "other-folder")
                elif mismatch == "brief": run["brief"]["revision"] = "other-candidate"
                elif mismatch == "agent": run["agent"] = None
                elif mismatch == "failed": run["state"] = "failed"
                self.write(root, "session-run.json", run); self.write(root, "browser.json", browser)
                self.assertEqual(self.invoke(root, "candidate-2", "http://127.0.0.1:4173", "--session-run", root / "session-run.json")[1]["status"], "invalid")


    def v2_session_record(self, name="v2"):
        root = self.session_record(name=name)
        brief = self.load(root, "qa/brief.json"); brief["version"] = 2
        run = self.load(root, "session-run.json"); run["brief"] = brief
        run["inputSha256"] = hashlib.sha256(json.dumps(brief, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        receipt = {"version": 1, "receiptId": run["id"] + ":summary:1", "qaId": run["id"],
                   "briefSha256": run["inputSha256"], "revision": brief["revision"], "grants": [], "audit": {}}
        raw = (json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
        (root / "host-summary.json").write_bytes(raw)
        report = self.load(root, "qa/report.json"); report["version"] = 2
        report["host_summary"] = {"receiptId": receipt["receiptId"], "sha256": hashlib.sha256(raw[:-1]).hexdigest()}
        run["accountsSealedAt"] = "2026-10-29T00:00:00Z"
        run["result"].update(report=report, hostSummary=receipt)
        self.write(root, "qa/brief.json", brief); self.write(root, "qa/report.json", report); self.write(root, "session-run.json", run)
        return root

    def test_v2_native_receipt_resumes_without_writes_and_reaches_shared_checker(self):
        root = self.v2_session_record()
        self.checker.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0 if '--host-summary' in sys.argv else 1)\n")
        before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        for _ in range(2):
            self.assertEqual(self.invoke(root, "candidate-2", "http://127.0.0.1:4173", "--session-run", root / "session-run.json")[1]["status"], "pass")
        self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_v2_receipt_cannot_borrow_or_modify_native_host_state(self):
        for mismatch in ["unsealed", "native", "digest", "foreign", "symlink"]:
            with self.subTest(mismatch=mismatch):
                root = self.v2_session_record(mismatch); run = self.load(root, "session-run.json")
                path = root / "host-summary.json"
                if mismatch == "unsealed": run.pop("accountsSealedAt")
                elif mismatch == "native": run["result"]["hostSummary"]["revision"] = "other"
                elif mismatch == "digest": path.write_text(path.read_text() + "\n")
                elif mismatch == "foreign":
                    receipt = self.load(root, "host-summary.json"); receipt["qaId"] = "foreign"
                    self.write(root, "host-summary.json", receipt)
                elif mismatch == "symlink":
                    other = root / "other.json"; path.rename(other); path.symlink_to(other)
                self.write(root, "session-run.json", run)
                self.assertEqual(self.invoke(root, "candidate-2", "http://127.0.0.1:4173", "--session-run", root / "session-run.json")[1]["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
