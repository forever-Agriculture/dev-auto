from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "install-dev-auto.py"
SOURCE = (REPO / "skills" / "dev-auto").resolve()
RELATIVE_DESTINATIONS = (
    Path(".agents/skills/dev-auto"),
    Path(".claude/skills/dev-auto"),
)


class InstallerTests(unittest.TestCase):
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

    def test_reinstall_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(self.run_installer(root).returncode, 0)
            before = {relative: (root / relative).lstat() for relative in RELATIVE_DESTINATIONS}

            repeated = self.run_installer(root)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            after = {relative: (root / relative).lstat() for relative in RELATIVE_DESTINATIONS}
            self.assertEqual(before, after)

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
