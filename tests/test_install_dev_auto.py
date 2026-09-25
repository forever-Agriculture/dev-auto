# MODULE: test_install_dev_auto.py - installer tests for links and hook registration
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "install-dev-auto.py"
SOURCE = (REPO / "skills" / "dev-auto").resolve()
HOOK = REPO / "hooks" / "dev-auto-session-start.py"
HOOK_FILES = (
    Path(".claude/settings.json"),
    Path(".codex/hooks.json"),
)
RELATIVE_DESTINATIONS = (
    Path(".agents/skills/dev-auto"),
    Path(".claude/skills/dev-auto"),
)


class InstallerTests(unittest.TestCase):
    def test_hook_parent_conflict_prevents_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocker = root / '.codex'
            blocker.write_text('user data\n', encoding='utf-8')
            result = self.run_installer(root)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('Nothing changed', result.stderr)
            self.assertEqual(blocker.read_text(), 'user data\n')
            self.assertEqual(list(root.iterdir()), [blocker])

    def run_installer(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--target-root", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_installs_both_links_and_check_accepts_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = self.run_installer(root)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            for relative in RELATIVE_DESTINATIONS:
                destination = root / relative
                self.assertTrue(destination.is_symlink())
                self.assertEqual(destination.resolve(strict=True), SOURCE)

            checked = self.run_installer(root, "--check")
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

    def test_registers_hook_in_both_clients_preserving_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            existing = {
                "model": "opus",
                "hooks": {
                    "SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": "echo hi"}]}],
                    "Stop": [{"hooks": [{"type": "command", "command": "echo bye"}]}],
                },
            }
            settings.write_text(json.dumps(existing), encoding="utf-8")

            result = self.run_installer(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            for relative in HOOK_FILES:
                data = json.loads((root / relative).read_text(encoding="utf-8"))
                groups = data["hooks"]["SessionStart"]
                ours = [g for g in groups if HOOK.name in g["hooks"][0]["command"]]
                self.assertEqual(len(ours), 1, relative)
                self.assertEqual(ours[0]["matcher"], "compact|resume")
                self.assertEqual(ours[0]["hooks"][0]["command"], f"python3 {HOOK}")
            claude = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(claude["model"], "opus")
            self.assertEqual(claude["hooks"]["Stop"], existing["hooks"]["Stop"])
            self.assertEqual(claude["hooks"]["SessionStart"][0], existing["hooks"]["SessionStart"][0])

            repeated = self.run_installer(root)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            again = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(again, claude)
            self.assertEqual(self.run_installer(root, "--check").returncode, 0)

    def test_glm_profile_gets_the_skill_and_hook_only_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            absent = self.run_installer(root)
            self.assertEqual(absent.returncode, 0, absent.stderr)
            self.assertIn("SKIPPED: no GLM profile", absent.stdout)
            self.assertFalse((root / ".claude-glm").exists())

            profile = root / ".claude-glm"
            profile.mkdir()
            (profile / "skills").symlink_to(root / ".claude" / "skills")  # the owner's layout
            settings = profile / "settings.json"
            settings.write_text(json.dumps({"model": "opus", "effortLevel": "high"}), encoding="utf-8")
            before = self.run_installer(root, "--check")
            self.assertEqual(before.returncode, 1, before.stdout)
            self.assertIn(f"HOOK MISSING: {settings}", before.stdout)
            self.assertIn(f"GLM EFFORT NOT MAX: {settings}", before.stdout)

            present = self.run_installer(root)
            self.assertEqual(present.returncode, 0, present.stderr)
            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual((data["model"], data["effortLevel"]), ("opus", "max"))
            self.assertEqual(len([g for g in data["hooks"]["SessionStart"]
                                  if HOOK.name in g["hooks"][0]["command"]]), 1)
            self.assertEqual((profile / "skills" / "dev-auto").resolve(strict=True), SOURCE)
            after = self.run_installer(root, "--check")
            self.assertEqual(after.returncode, 0, after.stdout + after.stderr)
            self.assertIn(f"HOOK OK: {settings}", after.stdout)
            self.assertIn(f"GLM EFFORT OK: {settings}", after.stdout)

    def test_glm_profile_regular_file_is_skipped_and_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glm = root / ".claude-glm"
            glm.write_text("profile data\n", encoding="utf-8")
            result = self.run_installer(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SKIPPED: no GLM profile", result.stdout)
            self.assertFalse(glm.is_symlink() or glm.is_dir())
            self.assertEqual(glm.read_text(encoding="utf-8"), "profile data\n")
            for relative in RELATIVE_DESTINATIONS:
                self.assertTrue((root / relative).is_symlink(), relative)

    def test_malformed_glm_settings_refuses_every_change(self) -> None:
        for broken in ("{broken", '{"hooks": {"SessionStart": "nope"}}'):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                settings = root / ".claude-glm" / "settings.json"
                settings.parent.mkdir(parents=True)
                settings.write_text(broken, encoding="utf-8")
                result = self.run_installer(root)
                self.assertEqual(result.returncode, 2, broken + result.stderr)
                self.assertIn(f"hook file unreadable: {settings}", result.stderr)
                self.assertIn("Nothing changed", result.stderr)
                self.assertEqual(settings.read_text(encoding="utf-8"), broken)
                self.assertEqual([path.name for path in root.iterdir()], [".claude-glm"])
                self.assertEqual([path.name for path in settings.parent.iterdir()], ["settings.json"])

    def test_glm_real_skills_directory_gets_link_and_hook(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills = root / ".claude-glm" / "skills"
            skills.mkdir(parents=True)
            result = self.run_installer(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            destination = skills / "dev-auto"
            self.assertTrue(destination.is_symlink())
            self.assertEqual(destination.resolve(strict=True), SOURCE)
            self.assertFalse(skills.is_symlink())  # the owner's real directory is kept, not replaced
            settings = root / ".claude-glm" / "settings.json"
            groups = json.loads(settings.read_text(encoding="utf-8"))["hooks"]["SessionStart"]
            self.assertEqual(len([g for g in groups if HOOK.name in g["hooks"][0]["command"]]), 1)
            checked = self.run_installer(root, "--check")
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn(f"HOOK OK: {settings}", checked.stdout)

    def test_links_only_leaves_glm_settings_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / ".claude-glm" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text('{"model": "opus"}\n', encoding="utf-8")
            result = self.run_installer(root, "--links-only")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(settings.read_text(encoding="utf-8"), '{"model": "opus"}\n')
            self.assertTrue((root / ".claude-glm" / "skills" / "dev-auto").is_symlink())
            for relative in HOOK_FILES:
                self.assertFalse((root / relative).exists(), relative)
            checked = self.run_installer(root, "--check")
            self.assertEqual(checked.returncode, 1, checked.stdout)
            self.assertIn(f"HOOK MISSING: {settings}", checked.stdout)

    def test_check_touches_nothing_with_glm_profile_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / ".claude-glm" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({"model": "opus"}), encoding="utf-8")

            def snapshot() -> dict:
                state = {}
                for path in sorted(root.rglob("*")):
                    if path.is_symlink():
                        value = f"link:{path.readlink()}"
                    elif path.is_dir():
                        value = "dir"
                    else:
                        value = path.read_bytes()
                    state[str(path.relative_to(root))] = value
                return state

            before = snapshot()
            result = self.run_installer(root, "--check")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(f"HOOK MISSING: {settings}", result.stdout)
            self.assertEqual(snapshot(), before)

    def test_conflicting_glm_skill_directory_refuses_the_whole_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            conflict = root / ".claude-glm" / "skills" / "dev-auto"
            conflict.mkdir(parents=True)
            sentinel = conflict / "keep.txt"
            sentinel.write_text("user data\n", encoding="utf-8")
            result = self.run_installer(root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "user data\n")
            for relative in RELATIVE_DESTINATIONS:
                self.assertFalse((root / relative).exists(), relative)
            self.assertFalse((root / ".claude" / "settings.json").exists())
            self.assertFalse((root / ".claude-glm" / "settings.json").exists())

    def test_links_only_skips_hooks_and_check_reports_them_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(self.run_installer(root, "--links-only").returncode, 0)
            for relative in HOOK_FILES:
                self.assertFalse((root / relative).exists())
            checked = self.run_installer(root, "--check")
            self.assertEqual(checked.returncode, 1)
            self.assertIn("HOOK MISSING", checked.stdout)

    def test_malformed_hook_file_is_preserved_and_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hooks = root / ".codex" / "hooks.json"
            hooks.parent.mkdir(parents=True)
            hooks.write_text("{broken", encoding="utf-8")
            result = self.run_installer(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("unreadable", result.stderr)
            self.assertEqual(hooks.read_text(encoding="utf-8"), "{broken")
            for relative in RELATIVE_DESTINATIONS:
                self.assertFalse((root / relative).exists())

    def test_type_mismatched_hook_shapes_are_refused_before_any_change(self) -> None:
        for shape in ('{"hooks": {"SessionStart": {"matcher": "startup"}}}', '{"hooks": []}', '[]'):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                settings = root / ".claude" / "settings.json"
                settings.parent.mkdir(parents=True)
                settings.write_text(shape, encoding="utf-8")
                result = self.run_installer(root)
                self.assertEqual(result.returncode, 2, shape + result.stderr)
                self.assertIn("Nothing changed", result.stderr)
                self.assertEqual(settings.read_text(encoding="utf-8"), shape)
                for relative in RELATIVE_DESTINATIONS:
                    self.assertFalse((root / relative).exists(), shape)

    def test_symlinked_settings_are_written_through_and_keep_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dotfile = root / "dotfiles" / "claude-settings.json"
            dotfile.parent.mkdir(parents=True)
            dotfile.write_text('{"model": "opus"}', encoding="utf-8")
            dotfile.chmod(0o664)
            settings = root / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.symlink_to(dotfile)
            result = self.run_installer(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(settings.is_symlink())
            data = json.loads(dotfile.read_text(encoding="utf-8"))
            self.assertEqual(data["model"], "opus")
            self.assertEqual(len(data["hooks"]["SessionStart"]), 1)
            self.assertEqual(dotfile.stat().st_mode & 0o777, 0o664)
            self.assertEqual(self.run_installer(root, "--check").returncode, 0)

    def test_hook_command_quotes_paths_with_spaces_and_metacharacters(self) -> None:
        import importlib.util
        import shlex

        spec = importlib.util.spec_from_file_location("installer", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        script = Path("/tmp/my checkout; rm -rf x/hooks/dev-auto-session-start.py")
        command = module.hook_group(script)["hooks"][0]["command"]
        self.assertEqual(shlex.split(command), ["python3", str(script)])

    def test_malformed_nested_group_is_skipped_not_crashed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text('{"hooks": {"SessionStart": [{"hooks": null}, 7]}}', encoding="utf-8")
            result = self.run_installer(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            groups = json.loads(settings.read_text(encoding="utf-8"))["hooks"]["SessionStart"]
            self.assertEqual(groups[:2], [{"hooks": None}, 7])
            self.assertEqual(len(groups), 3)

    def test_reinstall_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(self.run_installer(root).returncode, 0)
            def snapshot() -> dict:
                result = {}
                for relative in RELATIVE_DESTINATIONS:
                    path = root / relative
                    stat = path.lstat()
                    result[str(relative)] = (
                        stat.st_ino, stat.st_mode, stat.st_size,
                        stat.st_mtime_ns, stat.st_ctime_ns, path.readlink(),
                    )
                for relative in HOOK_FILES:
                    path = root / relative
                    stat = path.stat()
                    result[str(relative)] = (
                        stat.st_ino, stat.st_mode, stat.st_size,
                        stat.st_mtime_ns, stat.st_ctime_ns, path.read_bytes(),
                    )
                return result

            # Force an old access time: resolving a link may update it, without
            # changing the installation. Do not assert atime or sleep for a tick.
            for relative in RELATIVE_DESTINATIONS:
                path = root / relative
                os.utime(path, ns=(1_000_000_000, path.lstat().st_mtime_ns), follow_symlinks=False)
            before = snapshot()
            repeated = self.run_installer(root)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(before, snapshot())

    def test_existing_directory_is_preserved_and_prevents_partial_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            conflict = root / RELATIVE_DESTINATIONS[1]
            conflict.mkdir(parents=True)
            sentinel = conflict / "keep.txt"
            sentinel.write_text("user data\n", encoding="utf-8")

            result = self.run_installer(root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "user data\n")
            self.assertFalse((root / RELATIVE_DESTINATIONS[0]).exists())

    def test_conflicting_link_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            other = root / "other-skill"
            other.mkdir()
            conflict = root / RELATIVE_DESTINATIONS[0]
            conflict.parent.mkdir(parents=True)
            conflict.symlink_to(other, target_is_directory=True)

            result = self.run_installer(root)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(conflict.is_symlink())
            self.assertEqual(conflict.resolve(strict=True), other.resolve())
            self.assertFalse((root / RELATIVE_DESTINATIONS[1]).exists())

    def test_dangling_link_is_preserved_and_prevents_partial_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing_target = root / "missing-skill"
            conflict = root / RELATIVE_DESTINATIONS[0]
            conflict.parent.mkdir(parents=True)
            conflict.symlink_to(missing_target, target_is_directory=True)

            result = self.run_installer(root)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(conflict.is_symlink())
            self.assertEqual(conflict.readlink(), missing_target)
            self.assertFalse((root / RELATIVE_DESTINATIONS[1]).exists())

    def test_regular_file_parent_is_preserved_and_prevents_partial_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocker = root / ".claude"
            blocker.write_text("user data\n", encoding="utf-8")

            result = self.run_installer(root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(blocker.read_text(encoding="utf-8"), "user data\n")
            self.assertFalse((root / RELATIVE_DESTINATIONS[0]).exists())

    def test_check_is_read_only_when_links_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_installer(root, "--check")
            self.assertEqual(result.returncode, 1)
            for relative in RELATIVE_DESTINATIONS:
                self.assertFalse((root / relative).exists())


if __name__ == "__main__":
    unittest.main()
