# MODULE: test_check.py - red/green fixtures for the dev-auto acceptance lint and receipt reader
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "dev-auto" / "scripts" / "check.py"
TEMPLATE = REPO / "skills" / "dev-auto" / "assets" / "handoff.md"

CLEAN = (
    "# Dev Auto handoff\n\n"
    "- Lead host / requested model / observed model: Codex; gpt-5.6-sol/xhigh; gpt-5.6-sol/xhigh (rollout 01a0)\n"
    "- Explicit user stop (if any; only a later user instruction clears it): none\n\n"
    "## Measurement\n\n"
    "- Observed usage: lead 35,585,513 total tokens (rollout 01a0); helpers none\n\n"
    "## Resume\n\n"
    "- Status: COMPLETE\n"
)


def run(*args: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, env=env,
                          capture_output=True, text=True, check=False, timeout=30)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class Project:
    def __init__(self, body: str = CLEAN) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        (self.root / ".dev-auto").mkdir(parents=True)
        git(self.root, "init", "-q")
        self.write(body)

    def write(self, body: str) -> None:
        (self.root / ".dev-auto" / "handoff.md").write_text(body, encoding="utf-8")

    def track(self, rel: str, size: int = 10) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        git(self.root, "add", "-f", rel)


class CheckTests(unittest.TestCase):
    def project(self, body: str = CLEAN) -> Project:
        project = Project(body)
        self.addCleanup(project.tmp.cleanup)
        return project

    def test_complete_clean_handoff_passes(self) -> None:
        project = self.project()
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(result.stdout.startswith("PASS"))

    def test_placeholder_in_model_field_fails(self) -> None:
        # Reproduces the BMN Epics 6-7 miss: COMPLETE with the receipt still "to be recorded".
        body = CLEAN.replace("gpt-5.6-sol/xhigh (rollout 01a0)",
                             "current rollout receipt to be recorded at acceptance")
        project = self.project(body)
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("observed model' still holds placeholder", result.stdout)

    def test_template_text_and_empty_usage_fail(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8").replace(
            "- Status: ACTIVE | PAUSED | BLOCKED | COMPLETE", "- Status: COMPLETE")
        project = self.project(template)
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("observed model' still holds placeholder", result.stdout)
        project.write(CLEAN.replace("lead 35,585,513 total tokens (rollout 01a0); helpers none", ""))
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("'Observed usage' is empty", result.stdout)

    def test_tracked_raw_evidence_fails_and_untracked_passes(self) -> None:
        project = self.project()
        project.track(".dev-auto/review.jsonl")
        project.track(".dev-auto/evidence/shot.png")
        project.track(".dev-auto/big.md", size=300 * 1024)
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        for name in ("review.jsonl", "evidence/shot.png", "big.md"):
            self.assertIn(name, result.stdout)
        git(project.root, "rm", "-q", "--cached", ".dev-auto/review.jsonl",
            ".dev-auto/evidence/shot.png", ".dev-auto/big.md")
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_gaps_clause_filled_passes_and_empty_fails(self) -> None:
        project = self.project(CLEAN.replace("helpers none", "helpers none; gaps: none"))
        self.assertEqual(run("check", str(project.root)).returncode, 0)
        project.write(CLEAN.replace("helpers none", "helpers none; gaps:"))
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("'Observed usage' still holds placeholder", result.stdout)

    def test_annotated_complete_status_is_linted(self) -> None:
        body = CLEAN.replace("(rollout 01a0)", "to be recorded").replace(
            "- Status: COMPLETE", "- Status: COMPLETE (all epics accepted)")
        project = self.project(body)
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_large_handoff_itself_is_not_raw_evidence(self) -> None:
        project = self.project(CLEAN + "#" * (300 * 1024))
        git(project.root, "add", ".dev-auto/handoff.md")
        self.assertEqual(run("check", str(project.root)).returncode, 0)

    def test_non_complete_status_skips_even_with_placeholders(self) -> None:
        body = CLEAN.replace("(rollout 01a0)", "to be recorded").replace(
            "- Status: COMPLETE", "- Status: PAUSED (owner stop)")
        project = self.project(body)
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("SKIP: Status is PAUSED", result.stdout)

    def test_missing_handoff_is_unable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run("check", tmp)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertTrue(result.stdout.startswith("UNABLE"))

    def test_check_from_source_subdirectory(self) -> None:
        project = self.project()
        sub = project.root / "src" / "deep"
        sub.mkdir(parents=True)
        result = run("check", cwd=sub)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_dispatch_rows_enforce_first_tier_or_reason(self) -> None:
        def body(*rows: str) -> str:
            return CLEAN.replace("## Resume", "- Dispatches: rows\n" + "".join(f"  - {r}\n" for r in rows) + "\n## Resume")
        green = body("epic review | epic-review | gpt-6-astra/medium | rollout 01a1 | first",
                     "tests | routine | gpt-5.6-luna/max | rollout 01a2 | escalated: GLM route returned EAI_AGAIN twice",
                     "runtime scout | scout | gpt-5.6-luna/max | rollout 01a3 | first")
        self.assertEqual(run("check", str(self.project(green).root)).returncode, 0)
        for red, reason in [
            (body("review | routine | gpt-5.6-luna/max | rollout | first"), "first tier is glm-5.3-flash"),
            (body("debug | debugging | gpt-6-astra/high | rollout | first"), "first tier is glm-5.3"),
            (body("race review | complex | gpt-5.6-luna/max | rollout | first"), "first tier is glm-5.3"),
            (body("review | epic-review | fable/medium | receipt | escalated:"), "without a reason"),
            (body("full review / native fable / receipt"), "not in"),
            (body("review | epic-review | gpt-6-astra/medium | rollout | maybe"), "tier must be"),
        ]:
            result = run("check", str(self.project(red).root))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(reason, result.stdout)

    def test_no_dispatch_rows_is_not_a_failure(self) -> None:
        self.assertEqual(run("check", str(self.project(CLEAN.replace("## Resume", "- Dispatches: none\n\n## Resume")).root)).returncode, 0)


def rollout_lines(cwd: str, effort: str | None = "xhigh") -> list[str]:
    context = {"model": "gpt-5.6-sol", "cwd": cwd}
    if effort:
        context["effort"] = effort
    return [
        json.dumps({"timestamp": "2026-09-19T10:00:00Z", "type": "session_meta",
                    "payload": {"id": "abc", "cwd": cwd, "cli_version": "0.155.1", "originator": "codex-tui"}}),
        json.dumps({"timestamp": "2026-09-19T10:00:01Z", "type": "turn_context", "payload": context}),
        json.dumps({"timestamp": "2026-09-19T10:00:02Z", "type": "event_msg",
                    "payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 10}}}}),
        "not json",
        json.dumps({"timestamp": "2026-09-19T10:05:00Z", "type": "event_msg",
                    "payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 42}}}}),
    ]


class UsageTests(unittest.TestCase):
    def test_rollout_reports_route_and_last_cumulative_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-x.jsonl"
            path.write_text("\n".join(rollout_lines("/p")) + "\n", encoding="utf-8")
            result = run("usage", str(path))
            self.assertEqual(result.returncode, 0, result.stdout)
            info = json.loads(result.stdout)
        self.assertEqual(info["routes"], ["gpt-5.6-sol/xhigh"])
        self.assertEqual(info["total_token_usage"], {"total_tokens": 42})
        self.assertEqual((info["id"], info["cwd"], info["last"]), ("abc", "/p", "2026-09-19T10:05:00Z"))

    def test_missing_effort_stays_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-x.jsonl"
            path.write_text("\n".join(rollout_lines("/p", effort=None)) + "\n", encoding="utf-8")
            info = json.loads(run("usage", str(path)).stdout)
        self.assertEqual(info["routes"], ["gpt-5.6-sol/unavailable"])

    def test_claude_receipt(self) -> None:
        receipt = {"type": "result", "total_cost_usd": 0.03, "num_turns": 2,
                   "modelUsage": {"GLM-5.3-Flash": {"inputTokens": 5, "outputTokens": 1,
                                                    "costUSD": 0.03, "maxOutputTokens": 32000,
                                                    "provider": "firstParty"}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            info = json.loads(run("usage", str(path)).stdout)
        self.assertEqual(info["models"], ["GLM-5.3-Flash"])
        self.assertEqual(info["usage"]["GLM-5.3-Flash"], {"inputTokens": 5, "outputTokens": 1, "costUSD": 0.03})
        self.assertEqual(info["total_cost_usd"], 0.03)

    def test_unreadable_receipt_is_unable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            path.write_text("{broken", encoding="utf-8")
            result = run("usage", str(path))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertTrue(result.stdout.startswith("UNABLE"))
        self.assertEqual(run("usage").returncode, 2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-x.jsonl"
            path.write_text(json.dumps({"type": "turn_context", "payload": "not a dict"}) + "\n", encoding="utf-8")
            info = json.loads(run("usage", str(path)).stdout)
            self.assertEqual(info["routes"], ["unavailable"])
            path = Path(tmp) / "receipt.json"
            path.write_text(json.dumps({"modelUsage": {"m": "bad"}}), encoding="utf-8")
            self.assertEqual(run("usage", str(path)).returncode, 0)
            path.write_text("[1]", encoding="utf-8")
            result = run("usage", str(path))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertTrue(result.stdout.startswith("UNABLE"))

    def test_claude_transcript_keeps_last_usage_per_response(self) -> None:
        def line(mid: str, model: str, out: int, stamp: str, **extra: object) -> str:
            usage = {"input_tokens": 2, "output_tokens": out, "cache_read_input_tokens": 100,
                     "cache_creation_input_tokens": 10, "service_tier": "standard"}
            record = {"type": "assistant", "timestamp": stamp, "sessionId": "s1", "cwd": "/p",
                      "effort": "xhigh", "message": {"id": mid, "model": model, "usage": usage}}
            record.update(extra)
            return json.dumps(record)
        lines = [
            json.dumps({"type": "mode", "mode": "normal"}),
            line("m1", "claude-opus-5", 7, "2026-09-19T11:00:00Z"),      # streamed partial
            line("m1", "claude-opus-5", 179, "2026-09-19T11:00:01Z"),    # same response, final
            json.dumps({"type": "user", "message": {"role": "user"}}),
            line("m2", "claude-fable-5-1", 50, "2026-09-19T11:00:02Z", effort="medium"),
            "{broken",
            json.dumps({"type": "cost-state", "totalCostUSD": 1.5,
                        "modelUsage": {"claude-opus-5": {"costUSD": 1.0}, "claude-fable-5-1": {"costUSD": 0.5}}}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d25944ed.jsonl"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = run("usage", str(path))
            self.assertEqual(result.returncode, 0, result.stdout)
            info = json.loads(result.stdout)
        self.assertEqual(info["routes"], ["claude-opus-5/xhigh", "claude-fable-5-1/medium"])
        self.assertEqual(info["responses"], 2)
        self.assertEqual(info["usage"]["claude-opus-5"],
                         {"inputTokens": 2, "outputTokens": 179, "cacheReadInputTokens": 100,
                          "cacheCreationInputTokens": 10})
        self.assertEqual(info["usage"]["claude-fable-5-1"]["outputTokens"], 50)
        self.assertEqual((info["id"], info["cwd"], info["last"]), ("s1", "/p", "2026-09-19T11:00:02Z"))
        self.assertEqual(info["session_cost_state"]["total_cost_usd"], 1.5)

    def test_subagent_transcript_without_cost_state_and_empty_transcript(self) -> None:
        record = {"type": "assistant", "timestamp": "t", "message": {"id": "a", "model": "claude-fable-5-1",
                  "usage": {"output_tokens": 3}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agent-a9a9.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            info = json.loads(run("usage", str(path)).stdout)
            self.assertEqual(info["routes"], ["claude-fable-5-1/unavailable"])
            self.assertEqual(info["usage"]["claude-fable-5-1"]["outputTokens"], 3)
            self.assertNotIn("session_cost_state", info)
            path.write_text("\n", encoding="utf-8")
            info = json.loads(run("usage", str(path)).stdout)
            self.assertEqual((info["routes"], info["usage"]), (["unavailable"], "unavailable"))
            path.write_text(json.dumps({"type": "assistant", "message": "not a dict"}) + "\n", encoding="utf-8")
            self.assertEqual(run("usage", str(path)).returncode, 0)

    def test_list_matches_session_cwd_only_and_does_not_choose(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            day = Path(home) / ".codex" / "sessions" / "2026" / "09" / "19"
            day.mkdir(parents=True)
            project = Path(home) / "proj"
            project.mkdir()
            (day / "rollout-a.jsonl").write_text("\n".join(rollout_lines(str(project))), encoding="utf-8")
            (day / "rollout-b.jsonl").write_text("\n".join(rollout_lines(str(project))), encoding="utf-8")
            (day / "rollout-c.jsonl").write_text("\n".join(rollout_lines("/elsewhere")), encoding="utf-8")
            env = {**os.environ, "HOME": home}
            result = run("usage", "--list", str(project), env=env)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("rollout-a.jsonl", result.stdout)
        self.assertIn("rollout-b.jsonl", result.stdout)
        self.assertNotIn("rollout-c.jsonl", result.stdout)
        self.assertIn("2 rollout(s)", result.stdout)


if __name__ == "__main__":
    unittest.main()
