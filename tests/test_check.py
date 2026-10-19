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
    "- Lead sessions: rollout 01a0 (lead); helpers none\n\n"
    "## Resume\n\n"
    "- Next safe action: none\n"
    "- Status: COMPLETE\n"
)


def run(*args: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, env=env,
                          capture_output=True, text=True, check=False, timeout=30)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def exclude_run_state(root: Path) -> None:
    """What check.py's hint tells the lead to run: the shared, local exclude file."""
    path = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-path", "info/exclude"],
                          check=True, capture_output=True, text=True).stdout.strip()
    path = Path(path) if Path(path).is_absolute() else root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(".dev-auto/\n")


class Project:
    def __init__(self, body: str = CLEAN, excluded: bool = True) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        (self.root / ".dev-auto").mkdir(parents=True)
        git(self.root, "init", "-q")
        if excluded:
            exclude_run_state(self.root)
        self.write(body)

    def write(self, body: str) -> None:
        (self.root / ".dev-auto" / "handoff.md").write_text(body, encoding="utf-8")

    def track(self, rel: str, size: int = 10) -> None:
        """Commit a file under .dev-auto, as earlier work did."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        git(self.root, "add", "-f", rel)
        git(self.root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", rel)


class CheckTests(unittest.TestCase):
    def project(self, body: str = CLEAN, excluded: bool = True) -> Project:
        project = Project(body, excluded)
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
        project.write(CLEAN.replace("rollout 01a0 (lead); helpers none", ""))
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("'Lead sessions' is empty", result.stdout)
        project.write(CLEAN.replace("- Lead sessions: rollout 01a0 (lead); helpers none\n", ""))
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("'Lead sessions' is missing; add `- Lead sessions:`", result.stdout)

    def test_tracked_run_state_is_a_note_not_a_fail(self) -> None:
        # ProjectB 66 and 69 (2026-09-24, 09-28) reported COMPLETE over a FAIL for 70
        # files earlier epics had committed: a lead cannot remove them without a
        # repository change, so the gate named a condition nobody in the run could fix.
        project = self.project()
        for rel in (".dev-auto/log.md", ".dev-auto/review.jsonl", ".dev-auto/pilot-tools/judge.json"):
            project.track(rel)
        project.track(".dev-auto/big.md", size=300 * 1024)
        for status in ("COMPLETE", "ACTIVE"):
            body = CLEAN.replace("- Status: COMPLETE", f"- Status: {status}")
            project.write(body)
            result = run("check", str(project.root))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("NOTE: 4 tracked .dev-auto file(s)", result.stdout)
            self.assertIn("stage none of your changes", result.stdout)
        git(project.root, "rm", "-q", "--cached", "-r", ".dev-auto")
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("NOTE", result.stdout)

    def test_staged_run_state_fails_and_untracking_does_not(self) -> None:
        # `git add -A` and `commit -a` still stage files earlier work committed.
        project = self.project()
        project.track(".dev-auto/log.md")
        (project.root / ".dev-auto" / "log.md").write_text("new entry", encoding="utf-8")
        git(project.root, "add", "-u")
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("run state is staged for commit: `git restore --staged -- .dev-auto`", result.stdout)
        git(project.root, "restore", "--staged", "--", ".dev-auto")
        self.assertEqual(run("check", str(project.root)).returncode, 0)
        git(project.root, "rm", "-q", "--cached", ".dev-auto/log.md")  # the cleanup itself
        self.assertEqual(run("check", str(project.root)).returncode, 0)

    def test_run_state_must_be_ignored_at_any_status(self) -> None:
        # ProjectB 2026-09-26..28: tracked handoffs and logs conflicted on every epic PR
        # across parallel worktrees and carried a stale handoff into main.
        for status in ("ACTIVE", "COMPLETE"):
            project = self.project(CLEAN.replace("- Status: COMPLETE", f"- Status: {status}"),
                                   excluded=False)
            result = run("check", str(project.root))
            self.assertEqual(result.returncode, 1, (status, result.stdout))
            self.assertIn("`.dev-auto/` is not ignored by git", result.stdout)
            self.assertIn("rev-parse --git-path info/exclude", result.stdout)
            exclude_run_state(project.root)
            self.assertEqual(run("check", str(project.root)).returncode, 0, status)

    def test_one_exclude_line_covers_every_worktree(self) -> None:
        project = self.project(excluded=False)
        (project.root / "README").write_text("x", encoding="utf-8")
        git(project.root, "add", "README")
        git(project.root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
        linked = Path(project.tmp.name) / "linked"
        git(project.root, "worktree", "add", "-q", str(linked))
        (linked / ".dev-auto").mkdir()
        (linked / ".dev-auto" / "handoff.md").write_text(CLEAN, encoding="utf-8")
        self.assertEqual(run("check", str(linked)).returncode, 1)
        exclude_run_state(linked)  # run from the linked worktree, as a lead would
        self.assertEqual(run("check", str(linked)).returncode, 0)
        self.assertEqual(run("check", str(project.root)).returncode, 0)

    def test_missing_git_is_unable_not_a_pass(self) -> None:
        project = self.project()
        env = dict(os.environ, PATH=str(Path(project.tmp.name) / "no-bin"))
        result = run("check", str(project.root), env=env)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertTrue(result.stdout.startswith("UNABLE: git cannot report"), result.stdout)

    def test_outside_a_repository_nothing_can_be_committed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".dev-auto").mkdir()
            (Path(tmp) / ".dev-auto" / "handoff.md").write_text(CLEAN, encoding="utf-8")
            env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(Path(tmp).parent))
            result = run("check", tmp, env=env)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(result.stdout.startswith("PASS"), result.stdout)

    def test_gaps_clause_filled_passes_and_empty_fails(self) -> None:
        project = self.project(CLEAN.replace("helpers none", "helpers none; gaps: none"))
        self.assertEqual(run("check", str(project.root)).returncode, 0)
        project.write(CLEAN.replace("helpers none", "helpers none; gaps:"))
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("'Lead sessions' still holds placeholder", result.stdout)

    def test_annotated_complete_status_is_linted(self) -> None:
        body = CLEAN.replace("(rollout 01a0)", "to be recorded").replace(
            "- Status: COMPLETE", "- Status: COMPLETE (all epics accepted)")
        project = self.project(body)
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_complete_gate_mirrors_the_hook_silence_grammar(self) -> None:
        # GLM review 2026-09-21: `COMPLETE pending acceptance`, a retained stop, or a
        # trailing line after Status all PASSed here while the hook kept waking sessions.
        for body, reason in (
            (CLEAN.replace("- Status: COMPLETE", "- Status: COMPLETE pending acceptance"), "not `COMPLETE`"),
            (CLEAN.replace("- Status: COMPLETE", "- Status: COMPLETELY blocked"), "not `COMPLETE`"),
            (CLEAN.replace("clears it): none", "clears it): paused 09-14; resumed 09-15"), "must be `none`"),
            (CLEAN + "- Note: trailing\n", "last line"),
        ):
            with self.subTest(reason=reason):
                result = run("check", str(self.project(body).root))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(reason, result.stdout)
        annotated = CLEAN.replace("- Status: COMPLETE", "- Status: COMPLETE — all epics accepted").replace(
            "clears it): none", "clears it): none (cleared 09-15)")
        result = run("check", str(self.project(annotated).root))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_hook_and_check_share_one_terminal_grammar(self) -> None:
        import importlib.util
        def load(path: Path):
            spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            return module
        hook = load(REPO / "hooks" / "dev-auto-session-start.py")
        check = load(SCRIPT)
        for name in ("COMPLETE", "NO_STOP", "TERMINAL"):
            self.assertEqual(getattr(hook, name).pattern, getattr(check, name).pattern, name)

    def test_large_handoff_itself_is_not_raw_evidence(self) -> None:
        project = self.project(CLEAN.replace("## Resume", "#" * (300 * 1024) + "\n\n## Resume"))
        project.track(".dev-auto/other.md")
        result = run("check", str(project.root))
        self.assertEqual(result.stdout.count("\n- "), 1, result.stdout)  # only the size check fails
        self.assertIn("injects it whole only up to 9,000", result.stdout)

    def test_oversized_handoff_fails_at_any_status(self) -> None:
        # Reproduces ProjectB 2026-09-19: an ACTIVE 38k handoff injected no content after compaction.
        history = "- Arm result: " + "details " * 1_600 + "\n"
        for status in ("ACTIVE", "PAUSED (owner stop)", "COMPLETE"):
            body = CLEAN.replace("- Status: COMPLETE", f"- Status: {status}").replace("## Resume", history + "\n## Resume")
            result = run("check", str(self.project(body).root))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("injects it whole only up to 9,000", result.stdout)
        body = CLEAN.replace("- Status: COMPLETE", "- Status: ACTIVE")
        self.assertEqual(run("check", str(self.project(body).root)).returncode, 0)
        # Codex middle-truncated a 10,399-character hook output: 9,500 must fail too.
        mid = body.replace("## Resume", "- Arm result: " + "d" * 9_300 + "\n\n## Resume")
        self.assertLess(len(mid), 12_000)
        result = run("check", str(self.project(mid).root))
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_long_status_and_missing_or_duplicate_fields_fail_at_any_status(self) -> None:
        active = CLEAN.replace("- Status: COMPLETE", "- Status: ACTIVE")
        for body, reason in [
            (active.replace("- Status: ACTIVE", "- Status: ACTIVE — owner chose " + "terms " * 40), "Status is 2"),
            (active.replace("- Explicit user stop (if any; only a later user instruction clears it): none\n", ""),
             "one `- Explicit user stop:` field, found 0"),
            (active.replace("- Next safe action: none\n", ""), "one `- Next safe action:` field, found 0"),
            (active + "- Status: COMPLETE\n", "one `- Status:` field, found 2"),
        ]:
            result = run("check", str(self.project(body).root))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(reason, result.stdout)
        short = active.replace("- Status: ACTIVE", "- Status: BLOCKED — owner spend decision for arm 6")
        self.assertEqual(run("check", str(self.project(short).root)).returncode, 0)

    def test_non_complete_status_skips_even_with_placeholders(self) -> None:
        body = CLEAN.replace("(rollout 01a0)", "to be recorded").replace(
            "- Status: COMPLETE", "- Status: PAUSED (owner stop)")
        project = self.project(body)
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("SKIP: Status is PAUSED", result.stdout)

    @unittest.skipIf(os.geteuid() == 0, "root reads any file")
    def test_unreadable_handoff_is_unable_not_a_traceback(self) -> None:
        project = self.project()
        handoff = project.root / ".dev-auto" / "handoff.md"
        handoff.chmod(0)
        self.addCleanup(handoff.chmod, 0o644)
        result = run("check", str(project.root))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertTrue(result.stdout.startswith("UNABLE: cannot read"))
        self.assertNotIn("Traceback", result.stderr)

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

    def test_dispatch_lines_are_free_text(self) -> None:
        # Owner 2026-09-24 simplification: the tier lint is gone, so off-tier, inline or
        # unformatted dispatch notes no longer FAIL a finished handoff.
        body = CLEAN.replace("## Resume", "- Dispatches: review | routine | gpt-6-astra/low | r | first\n"
                             "  - GLM pre-review: helper strong with final checks, receipt r2; Astra/medium epic review\n\n## Resume")
        self.assertEqual(run("check", str(self.project(body).root)).returncode, 0)

    def test_help_flags_print_help_instead_of_reading_a_path(self) -> None:
        for args in (("usage", "--help"), ("check", "-h"), ("--help",)):
            result = run(*args)
            self.assertEqual(result.returncode, 0, (args, result.stdout))
            self.assertIn("usage PATH", result.stdout)


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
        self.assertEqual(info["permissions"], [{"sandbox_policy": "unavailable", "approval_policy": "unavailable"}])
        self.assertEqual(info["total_token_usage"], {"total_tokens": 42})
        self.assertEqual((info["id"], info["cwd"], info["last"]), ("abc", "/p", "2026-09-19T10:05:00Z"))
        self.assertEqual(info["owner_turns"]["count"], 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-x.jsonl"
            turn = json.dumps({"type": "event_msg", "payload": {"type": "task_started"}})
            path.write_text("\n".join([*rollout_lines("/p"), turn, turn]) + "\n", encoding="utf-8")
            self.assertEqual(json.loads(run("usage", str(path)).stdout)["owner_turns"]["count"], 2)

    def test_rollout_reports_permission_changes_without_hiding_write_access(self) -> None:
        policies = [
            {"sandbox_policy": {"type": "workspace-write", "network_access": False}, "approval_policy": "on-request"},
            {"sandbox_policy": {"type": "read-only"}, "approval_policy": "on-request"},
            {"sandbox_policy": {"type": "read-only"}, "approval_policy": "never"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-x.jsonl"
            rows = rollout_lines("/p")
            for policy in [*policies, policies[0]]:
                rows.append(json.dumps({"type": "turn_context", "payload": policy}))
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            info = json.loads(run("usage", str(path)).stdout)
        self.assertEqual(info["permissions"], [
            {"sandbox_policy": "unavailable", "approval_policy": "unavailable"}, *policies])

    def test_list_skips_rollout_whose_first_line_is_not_an_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sessions = Path(directory) / "sessions"
            sessions.mkdir()
            (sessions / "rollout-bad.jsonl").write_text("5\n", encoding="utf-8")
            env = dict(os.environ, HOME=directory)
            result = run("usage", "--list", directory, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_missing_effort_stays_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-x.jsonl"
            path.write_text("\n".join(rollout_lines("/p", effort=None)) + "\n", encoding="utf-8")
            info = json.loads(run("usage", str(path)).stdout)
        self.assertEqual(info["routes"], ["gpt-5.6-sol/unavailable"])

    def test_unreadable_or_unknown_record_is_unable(self) -> None:
        self.assertEqual(run("usage").returncode, 2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-x.jsonl"
            path.write_text(json.dumps({"type": "turn_context", "payload": "not a dict"}) + "\n", encoding="utf-8")
            info = json.loads(run("usage", str(path)).stdout)
            self.assertEqual(info["routes"], ["unavailable"])
            # A lone .json file is no record this reads: Claude receipts and OpenCode exports went with their routes.
            path = Path(tmp) / "receipt.json"
            path.write_text(json.dumps({"modelUsage": {"m": {"inputTokens": 1}}}), encoding="utf-8")
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
            # Owner prompts: one typed, one queued mid-turn; a tool result, a task
            # notification and a queued notification are not the owner.
            json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "go"}}),
            json.dumps({"type": "attachment", "attachment": {"type": "queued_command", "prompt": "also",
                                                             "origin": {"kind": "human"}}}),
            json.dumps({"type": "user", "message": {"content": [{"type": "tool_result"}]}}),
            json.dumps({"type": "user", "origin": {"kind": "task-notification"}, "message": {"content": "t"}}),
            json.dumps({"type": "attachment", "attachment": {"type": "queued_command", "prompt": "n"}}),
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
        self.assertEqual(info["owner_prompts"]["count"], 2)

    def test_bmn_ask_export_counts_usage_once_by_its_basis(self) -> None:
        # Shapes of BMN 72.9's export (request.json, outcome.json); values made up.
        request = {"version": 1, "id": "20261015T170633-0000made", "role": "epic-reviewer", "agent": "astra",
                   "model": "gpt-6-astra", "effort": "medium", "chosen_by": "chain", "form": "codex-read-only",
                   "project": "/made/up/project"}
        outcome = {"version": 1, "id": "20261015T170633-0000made", "state": "answered", "exit": 0,
                   "observed": {"session": "01a1-made-up", "model": "gpt-6-astra", "effort": "medium"},
                   "subagents": [{"session": "01a2-made-up", "name": "Feynman", "kind": "Codex sub-agent",
                                  "model": "gpt-6-astra", "effort": "medium",
                                  "usage": {"input_tokens": 39001, "output_tokens": 138}}],
                   "usage": {"input_tokens": 174358, "output_tokens": 2078, "billing": "subscription",
                             "aggregation": "the teammate's own turns plus each sub-agent's own rollout",
                             "complete": True},
                   "started_at": "2026-10-15T17:06:36.039Z", "ended_at": "2026-10-15T17:06:50.978Z"}
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "ask"
            bundle.mkdir()
            (bundle / "request.json").write_text(json.dumps(request), encoding="utf-8")
            (bundle / "outcome.json").write_text(json.dumps(outcome), encoding="utf-8")
            info = json.loads(run("usage", str(bundle)).stdout)
            self.assertEqual((info["id"], info["state"], info["exit"], info["role"], info["agent"], info["form"]),
                             ("20261015T170633-0000made", "answered", 0, "epic-reviewer", "astra", "codex-read-only"))
            self.assertEqual((info["requested"], info["routes"], info["session"]),
                             ("gpt-6-astra/medium", ["gpt-6-astra/medium"], "01a1-made-up"))
            # BMN's total stands; the sub-agent's own count is shown, never added to it.
            self.assertEqual(info["usage"], outcome["usage"])
            self.assertEqual(info["subagents"][0]["usage"], {"input_tokens": 39001, "output_tokens": 138})
            # A folder that is not an export, and a broken one, are UNABLE.
            (bundle / "outcome.json").write_text("{broken", encoding="utf-8")
            result = run("usage", str(bundle))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertTrue(result.stdout.startswith("UNABLE"))
            result = run("usage", tmp)
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("ask export", result.stdout)

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


class AwayTests(unittest.TestCase):
    """`check.py away`: BMN's state beside the handoff's last confirmed one (BMN Story 76.7)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.project = Project(CLEAN.replace("- Status: COMPLETE", "- Status: ACTIVE"))
        self.addCleanup(self.project.tmp.cleanup)

    def bmn(self, stdout: str = "", code: int = 0, stderr: str = "") -> None:
        script = self.bin / "bmn"
        script.write_text("#!/bin/sh\n"
                          f"[ \"$*\" = \"away --status --json\" ] || exit 9\n"
                          f"printf '%s' {json.dumps(stdout)}\nprintf '%s' {json.dumps(stderr)} >&2\nexit {code}\n",
                          encoding="utf-8")
        script.chmod(0o755)

    def away(self, held: str | None = None, socket: bool = True) -> subprocess.CompletedProcess[str]:
        body = CLEAN.replace("- Status: COMPLETE", "- Status: ACTIVE")
        if held is not None:
            body = body.replace("- Explicit user stop", f"- BMN away: {held}\n- Explicit user stop")
        self.project.write(body)
        env = {k: v for k, v in os.environ.items() if k not in ("BMN_CONTROL_SOCKET", "AITERM_CONTROL_SOCKET")}
        env["PATH"] = f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin"
        if socket:
            env["BMN_CONTROL_SOCKET"] = "/nonexistent/control.sock"
        return run("away", str(self.project.root), env=env)

    def state(self, state: str, revision: int, since: str | None = "2026-10-16T19:10:00.000Z") -> str:
        return json.dumps({"state": state, "since": since, "revision": revision})

    def test_an_away_set_in_bmn_is_adopted_without_a_departure_card(self) -> None:
        self.bmn(self.state("away", 3))
        result = self.away()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("AWAY: away since 2026-10-16T19:10:00.000Z revision 3; ADOPT: set "
                      "`- BMN away: away since 2026-10-16T19:10:00.000Z revision 3`", result.stdout)
        self.assertIn("no departure statement or card", result.stdout)
        current = self.away("away since 2026-10-16T19:10:00.000Z revision 3")
        self.assertIn("AWAY: away since 2026-10-16T19:10:00.000Z revision 3; the handoff is current", current.stdout)
        self.assertNotIn("ADOPT", current.stdout)

    def test_back_in_bmn_ends_away_mode(self) -> None:
        self.bmn(self.state("back", 4))
        result = self.away("away since 2026-10-16T19:10:00.000Z revision 3")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("BACK: back since 2026-10-16T19:10:00.000Z revision 4; ADOPT:", result.stdout)
        self.assertIn("away mode ends", result.stdout)

    def test_bmn_missing_keeps_the_local_away_mode(self) -> None:
        result = self.away("away since 2026-10-16T19:10:00.000Z revision 3")  # no bmn on PATH
        self.assertEqual((result.returncode, result.stdout.split(":")[0]), (0, "MISSING"), result.stdout)
        self.bmn(self.state("away", 3))
        self.assertTrue(self.away(socket=False).stdout.startswith("MISSING"))  # not inside a BMN session
        self.bmn(code=2, stderr="bmn: unknown option --status\n")  # a BMN from before the away state
        self.assertTrue(self.away().stdout.startswith("MISSING"))

    def test_a_failed_read_is_unavailable_not_back_and_recovers_both_ways(self) -> None:
        held = "away since 2026-10-16T19:10:00.000Z revision 3"
        self.bmn(code=1, stderr="bmn: IO_ERROR: connect ECONNREFUSED\n")
        failed = self.away(held)
        self.assertEqual(failed.returncode, 2, failed.stdout)
        self.assertIn("UNAVAILABLE: bmn away --status failed (exit 1): bmn: IO_ERROR", failed.stdout)
        self.assertIn("the last confirmed state holds (away since 2026-10-16T19:10:00.000Z, revision 3), not back",
                      failed.stdout)
        self.bmn("not json")
        self.assertEqual(self.away(held).returncode, 2)
        self.bmn(self.state("back", 1))  # another BMN or a reset store: never read as back
        regressed = self.away(held)
        self.assertEqual(regressed.returncode, 2, regressed.stdout)
        self.assertIn("older than the confirmed 3", regressed.stdout)
        self.bmn(self.state("away", 3))
        self.assertIn("the handoff is current", self.away(held).stdout)
        self.bmn(self.state("back", 4))
        self.assertTrue(self.away(held).stdout.startswith("BACK: "))
        self.bmn(code=1, stderr="bmn: IO_ERROR: lost\n")
        self.assertIn("holds (back since 2026-10-17T05:00:00.000Z, revision 4)",
                      self.away("back since 2026-10-17T05:00:00.000Z revision 4").stdout)

    def test_template_field_reads_as_nothing_confirmed(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("- BMN away: none (", template)
        self.assertIn("- Run id: ", template)
        self.project.write(template)
        self.bmn(self.state("none", 0, since=None))
        env = {**os.environ, "PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin", "BMN_CONTROL_SOCKET": "/x"}
        result = run("away", str(self.project.root), env=env)
        self.assertIn("NONE: none since - revision 0; the handoff is current", result.stdout)


class GrantTests(unittest.TestCase):
    """`check.py grant`: the run's Away grant read fresh from BMN, never from the handoff (BMN Story 84.5 AC2)."""

    RUN = "dev-auto-epic-80-20261019"

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        body = CLEAN.replace("- Status: COMPLETE", "- Status: ACTIVE").replace(
            "- Explicit user stop", f"- Run id: {self.RUN}\n- Grant: 4 rounds per boundary (a stale copy)\n- Explicit user stop")
        self.project = Project(body)
        self.addCleanup(self.project.tmp.cleanup)

    def bmn(self, stdout: str = "", code: int = 0, stderr: str = "") -> None:
        script = self.bin / "bmn"
        script.write_text("#!/bin/sh\n"
                          f"[ \"$*\" = \"grant --run {self.RUN} --json\" ] || exit 9\n"
                          f"printf '%s' {json.dumps(stdout)}\nprintf '%s' {json.dumps(stderr)} >&2\nexit {code}\n",
                          encoding="utf-8")
        script.chmod(0o755)

    def grant(self, socket: bool = True) -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if k not in ("BMN_CONTROL_SOCKET", "AITERM_CONTROL_SOCKET")}
        env["PATH"] = f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin"
        if socket:
            env["BMN_CONTROL_SOCKET"] = "/nonexistent/control.sock"
        return run("grant", str(self.project.root), env=env)

    def answer(self, active: bool, lines: list[str], reason: str | None = None) -> str:
        entry = {"runId": self.RUN, "active": active, "lines": lines, **({} if reason is None else {"reason": reason})}
        return json.dumps({"departure": None, "runs": [entry]})

    def test_an_active_grant_prints_bmns_lines(self) -> None:
        lines = [f"Grant for run {self.RUN} (Epic 80), period p-1, while the owner is away; answered on Telegram.",
                 "  Extra repair rounds: 3 per boundary; epic-80: 1 of 3 used."]
        self.bmn(self.answer(True, lines))
        result = self.grant()
        self.assertEqual(result.returncode, 0, result.stdout)
        printed, order = result.stdout.rstrip("\n").rsplit("\n", 1)
        self.assertEqual(printed, "GRANT: " + "\n".join(lines))
        # BMN Epic 84's recheck: the order is printed where the lead reads the grant, right before the step.
        self.assertTrue(order.startswith("ORDER: at a parked boundary, save the evidence and agreed method in the brake record"), order)
        self.assertIn("report its outcome with `bmn grant report --period`", order)

    def test_no_grant_says_why_and_the_handoff_grants_nothing(self) -> None:
        reason = "the owner is back; every grant ended at 07:40"
        self.bmn(self.answer(False, [f"No grant for run {self.RUN}: {reason}."], reason))
        result = self.grant()
        self.assertEqual((result.returncode, result.stdout), (0, f"NO GRANT: {reason}\n"))
        self.assertNotIn("4 rounds", result.stdout)

    def test_missing_bmn_or_an_older_bmn_is_no_grant(self) -> None:
        self.assertEqual(self.grant().stdout, "MISSING: no bmn command or BMN session; NO GRANT: nothing is granted\n")
        self.bmn(self.answer(True, ["Grant."]))
        self.assertTrue(self.grant(socket=False).stdout.startswith("MISSING"))
        self.bmn(code=2, stderr="bmn: unknown command grant\nRun \"bmn help\" for usage.\n")
        self.assertEqual(self.grant().stdout, "MISSING: this BMN has no Away grant; NO GRANT: nothing is granted\n")

    def test_a_failed_read_is_unavailable_and_grants_nothing(self) -> None:
        self.bmn(code=1, stderr="bmn: the grant could not be read (IO_ERROR); nothing is granted\n")
        failed = self.grant()
        self.assertEqual(failed.returncode, 2, failed.stdout)
        self.assertIn("UNAVAILABLE: bmn grant failed (exit 1): bmn: the grant could not be read", failed.stdout)
        self.assertIn("NO GRANT: nothing is granted", failed.stdout)
        self.bmn("not json")
        self.assertEqual(self.grant().returncode, 2)
        self.bmn(json.dumps({"runs": []}))
        self.assertEqual(self.grant().returncode, 2)

    def test_a_handoff_without_a_run_id_is_unable(self) -> None:
        self.project.write(CLEAN.replace("- Status: COMPLETE", "- Status: ACTIVE"))
        self.bmn(self.answer(True, ["Grant."]))
        result = self.grant()
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stdout.startswith("UNABLE: the handoff has no `- Run id:`"))


if __name__ == "__main__":
    unittest.main()
