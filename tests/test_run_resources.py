# MODULE: test_run_resources.py - launch identity, discovery and worktree safety regressions
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/dev-auto/scripts/check.py"
spec = importlib.util.spec_from_file_location("resources", SCRIPT.with_name("run_resources.py"))
resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resources)


class LeftoversTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "run"
        self.root.mkdir()
        self.proc = Path(self.tmp.name) / "proc"
        self.proc.mkdir()

    def process(self, pid, cwd, args, ticks="123", ppid=1):
        path = self.proc / str(pid)
        path.mkdir()
        # /proc stat fields 3..22; a comm with spaces and ')' must still parse.
        (path / "stat").write_text(f"{pid} (fixture ) name) S {ppid} " + "0 " * 17 + ticks)
        (path / "cmdline").write_bytes("\0".join(args).encode() + b"\0")
        (path / "cwd").symlink_to(cwd)

    def test_owned_daemon_found_after_chdir_and_pid_reuse_not_owned(self):
        self.process(10001, "/", ["fixture-daemon"])
        entries = [{"kind": "process", "pid": 10001, "start_ticks": "123", "command": "fixture-daemon"}]
        owned, candidates = resources.inventory(self.root, entries, self.proc)
        self.assertEqual([p["pid"] for p in owned], [10001])
        self.assertFalse(candidates)
        entries[0]["start_ticks"] = "122"
        self.assertEqual(resources.inventory(self.root, entries, self.proc), ([], []))

    def test_path_candidates_are_bounded_and_never_owned(self):
        self.process(10001, str(self.root), ["server"])
        self.process(10002, "/", ["python", str(self.root / "serve.py")])
        self.process(10003, str(self.root) + "-sibling", ["server"])
        self.process(10004, "/", ["other-daemon"])
        owned, candidates = resources.inventory(self.root, [], self.proc)
        self.assertFalse(owned)
        self.assertEqual({p["pid"] for p in candidates}, {10001, 10002})

    def test_checker_ancestors_and_bmn_are_excluded_even_if_recorded(self):
        self.process(os.getpid(), str(self.root), ["check.py"], ppid=10002)
        self.process(10002, str(self.root), ["codex"])
        self.process(10003, str(self.root), ["/opt/BMN/bmn"])
        entries = [{"kind": "process", "pid": 10003, "start_ticks": "123", "command": "bmn"}]
        self.assertEqual(resources.inventory(self.root, entries, self.proc), ([], []))

    def test_packaging_directory_does_not_hide_an_owned_server(self):
        self.process(10001, "/", ["python", str(self.root / "release/linux-unpacked/fixture_server.py")])
        entries = [{"kind": "process", "pid": 10001, "start_ticks": "123", "command": "synthetic server"}]
        owned, candidates = resources.inventory(self.root, entries, self.proc)
        self.assertEqual([p["pid"] for p in owned], [10001])
        self.assertFalse(candidates)

    def test_owned_container_without_mounts_and_unowned_mount_candidate(self):
        def container(identity, name, mounts):
            return {"Id": identity, "Name": name, "State": {"Running": True}, "Path": "sleep",
                    "Args": ["300"], "Mounts": mounts}
        entries = [{"kind": "container", "id": "a" * 64, "name": "mine", "command": "fixture"}]
        containers = [container("a" * 64, "/mine", []),
                      container("b" * 64, "/candidate", [{"Source": str(self.root)}]),
                      container("c" * 64, "/other", [{"Source": str(self.root) + "-sibling"}])]
        owned, candidates = resources.inventory(self.root, entries, self.proc, containers)
        self.assertEqual([c["name"] for c in owned], ["mine"])
        self.assertEqual([c["name"] for c in candidates], ["candidate"])
        entries[0]["name"] = "renamed"
        self.assertFalse(resources.inventory(self.root, entries, self.proc, containers)[0])

    def test_started_rejects_partial_identities_and_reads_only_section(self):
        entry = {"kind": "process", "pid": 42, "start_ticks": "123", "command": "sleep 30"}
        self.assertEqual(resources.started("## Started\n- " + json.dumps(entry) + "\n## Resume\n- nonsense"), [entry])
        for entry in ({"kind": "process", "pid": 42, "command": "x"},
                      {"kind": "container", "id": "abc", "name": "x", "command": "x"}):
            with self.assertRaises(ValueError):
                resources.started("## Started\n- " + json.dumps(entry))

    def test_secrets_masked_in_display(self):
        text = resources.safe_command(["serve", "--token", "secret-value", "API_KEY=key-value", "https://name:pass@fixture.invalid"])
        self.assertNotIn("secret-value", text)
        self.assertNotIn("key-value", text)
        self.assertNotIn("name:pass", text)
        self.assertNotIn("Bearer-private", resources.safe_command(["serve", "-H", "Authorization: Bearer-private"]))

    def test_unavailable_docker_does_not_claim_complete_inventory(self):
        (self.root / ".dev-auto").mkdir()
        (self.root / ".dev-auto/handoff.md").write_text("## Started\n- none\n")
        with patch.object(resources.shutil, "which", return_value=None), patch("builtins.print") as output:
            self.assertEqual(resources.leftovers(self.root), 2)
        self.assertIn("UNABLE", str(output.call_args_list))

    def test_inaccessible_process_is_not_silently_absent(self):
        with patch.object(Path, "read_text", side_effect=PermissionError("synthetic denial")):
            with self.assertRaises(PermissionError):
                resources.process(os.getpid())

    def test_shell_command_operand_path_is_a_candidate(self):
        self.process(10001, "/", ["bash", "-c", f"python {self.root}/server.py"])
        owned, candidates = resources.inventory(self.root, [], self.proc)
        self.assertFalse(owned)
        self.assertEqual([p["pid"] for p in candidates], [10001])

    def test_real_child_is_reported_without_signal_or_file_change(self):
        (self.root / ".dev-auto").mkdir()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=self.root)
        self.addCleanup(lambda: (child.terminate(), child.wait()) if child.poll() is None else None)
        item = resources.process(child.pid)
        entry = {"kind": "process", "pid": child.pid, "start_ticks": item["start_ticks"], "command": "synthetic sleeper"}
        handoff = self.root / ".dev-auto/handoff.md"
        body = "## Started\n- " + json.dumps(entry)
        handoff.write_text(body)
        with patch.object(resources.shutil, "which", return_value="docker"), patch.object(resources, "command", return_value=""), patch("builtins.print") as output:
            code = resources.leftovers(self.root)
        # Host-owned same-uid processes may deny /proc reads (e.g. non-dumpable
        # desktop services). That makes the global inventory partial, not the
        # recorded child's identity unavailable. Never weaken the inventory guard.
        self.assertIn(code, (0, 2))
        if code == 2:
            self.assertIn("inventory partial", str(output.call_args_list))
        self.assertIsNone(child.poll())
        self.assertEqual(handoff.read_text(), body)
        self.assertTrue(any(f"pid={child.pid}" in str(c) for c in output.call_args_list))


class WorktreeTests(unittest.TestCase):
    def test_real_worktree_lifecycle_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout
            git("init", "-q", "-b", "main")
            git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "base")
            tree = Path(tmp) / "finished"
            git("worktree", "add", "-b", "finished", str(tree))
            git("config", "core.excludesFile", str(Path(tmp) / "ignore"))
            (Path(tmp) / "ignore").write_text(".dev-auto/\n")
            (tree / ".dev-auto").mkdir()
            handoff = tree / ".dev-auto/handoff.md"
            handoff.write_text("- Explicit user stop: none\n- Status: COMPLETE\n")
            def listing():
                result = subprocess.run([sys.executable, str(SCRIPT), "worktrees", str(root)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return {r["path"]: r for r in map(json.loads, result.stdout.splitlines())}
            rows = listing()
            self.assertEqual(rows[str(tree)]["action"], "may ask owner")
            self.assertEqual(rows[str(tree)]["branch"], "finished")
            self.assertEqual(rows[str(root)]["action"], "keep")
            self.assertGreater(rows[str(tree)]["bytes"], 0)
            handoff.write_text("- Explicit user stop: none\n- Status: ACTIVE\n")
            self.assertEqual(listing()[str(tree)]["action"], "keep")
            handoff.write_text("- Explicit user stop: none\n  Keep this run paused until I return\n- Status: COMPLETE\n")
            self.assertEqual(listing()[str(tree)]["action"], "keep")
            recovery = subprocess.run([sys.executable, str(REPO / "hooks/dev-auto-session-start.py")],
                                      input=json.dumps({"source": "compact", "cwd": str(tree)}),
                                      capture_output=True, text=True, check=True)
            self.assertIn("Keep this run paused", recovery.stdout)
            handoff.write_text("- Explicit user stop: none\n- Status: COMPLETE\n")
            (tree / "uncommitted").write_text("preserve")
            (tree / "nested").mkdir()
            (tree / "nested/one").write_text("one")
            (tree / "nested/two").write_text("two")
            row = listing()[str(tree)]
            self.assertEqual(row["uncommitted"], 3)
            self.assertEqual(row["action"], "keep")
            self.assertEqual((tree / "uncommitted").read_text(), "preserve")
            subprocess.run(["git", "-C", str(tree), "add", "uncommitted"], check=True)
            subprocess.run(["git", "-C", str(tree), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "not merged"], check=True)
            self.assertEqual(listing()[str(tree)]["ancestry"], "not merged")
            self.assertEqual(listing()[str(tree)]["action"], "keep")

    def test_rename_counts_as_one_change(self):
        self.assertEqual(resources.dirty_count("R  new\0old\0?? extra\0"), 2)

    def test_master_only_without_origin_head_and_index_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout
            git("init", "-q", "-b", "master")
            (root / "tracked").write_text("same content")
            git("add", "tracked")
            git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "base")
            # Force stale index stat-cache data without changing the tracked contents.
            os.utime(root / "tracked", (1, 1))
            index = root / ".git/index"
            before = (index.read_bytes(), index.stat().st_mtime_ns)
            result = subprocess.run([sys.executable, str(SCRIPT), "worktrees", str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            row = json.loads(result.stdout)
            self.assertEqual(row["ancestry"], "ancestor of master")
            self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)

    def test_main_inventory_does_not_refresh_stale_index(self):
        # Same real index probe as above, with the branch the original code supports.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
            git("init", "-q", "-b", "main")
            (root / "tracked").write_text("same content")
            git("add", "tracked")
            git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "base")
            os.utime(root / "tracked", (1, 1))
            index = root / ".git/index"
            before = (index.read_bytes(), index.stat().st_mtime_ns)
            result = subprocess.run([sys.executable, str(SCRIPT), "worktrees", str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)

    def test_unresolved_default_still_lists_each_worktree_as_keep(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
            git("init", "-q", "-b", "alpha")
            git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "base")
            git("branch", "beta")
            result = subprocess.run([sys.executable, str(SCRIPT), "worktrees", str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            row = json.loads(result.stdout)
            self.assertEqual(row["ancestry"], "unknown default branch")
            self.assertEqual(row["action"], "keep")


if __name__ == "__main__":
    unittest.main()
