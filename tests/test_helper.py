# MODULE: test_helper.py - offline checks of the helper provider wrapper's permission scoping
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "dev-auto" / "scripts" / "helper.sh"
# The provider lines at the top of the script, so a provider switch never edits these tests.
CONFIG = dict(re.findall(r'^(PROFILE|FAST|STRONG)="?([^"\n]+)"?$', SCRIPT.read_text(), re.MULTILINE))
FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
print(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin": sys.stdin.read(),
                  "sonnet": os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL"),
                  "opus": os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL"),
                  "profile": os.environ.get("FAKE_PROFILE")}))
"""


class HelperTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        profile = Path(CONFIG["PROFILE"].replace("$HOME", str(root / "home")))
        profile.parent.mkdir(parents=True)
        profile.write_text("export FAKE_PROFILE=loaded FAKE_SECRET=s3cr3t-value\n")
        (root / "bin").mkdir()
        claude = root / "bin" / "claude"
        claude.write_text(FAKE_CLAUDE)
        claude.chmod(0o755)
        self.project = root / "project"
        self.project.mkdir()
        self.prompt = root / "prompt.md"
        self.prompt.write_text("review this")
        self.output = root / "out.json"
        self.env = {**os.environ, "HOME": str(root / "home"),
                    "PATH": f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}"}

    def run_helper(self, *args: str, trace: bool = False) -> subprocess.CompletedProcess[str]:
        command = ["bash", *(["-x"] if trace else []), str(SCRIPT), *args]
        return subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=30)

    def call(self, mode: str, tier: str, *check: str) -> dict:
        result = self.run_helper(mode, tier, str(self.project), str(self.prompt), str(self.output), *check)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.output.read_text())

    @staticmethod
    def values(argv: list[str], flag: str) -> list[str]:
        start = argv.index(flag) + 1
        end = next((i for i in range(start, len(argv)) if argv[i].startswith("--")), len(argv))
        return argv[start:end]

    def test_review_reads_only_inside_the_project(self) -> None:
        seen = self.call("review", "fast")
        argv = seen["argv"]
        self.assertEqual((seen["cwd"], seen["stdin"], seen["profile"]), (str(self.project), "review this", "loaded"))
        self.assertEqual(self.values(argv, "--model"), ["sonnet"])
        self.assertEqual(seen["sonnet"], CONFIG["FAST"])
        self.assertEqual(self.values(argv, "--tools"), ["Read,Glob,Grep"])
        self.assertEqual(self.values(argv, "--allowedTools"), ["Read(./**)"])
        self.assertEqual(self.values(argv, "--disallowedTools"), ["Read(./**/.env*)", "Edit(./**/.env*)"])
        self.assertEqual(self.values(argv, "--permission-mode"), ["dontAsk"])
        self.assertNotIn("--settings", argv)

    def test_edit_with_check_scopes_edits_and_sandboxes_the_one_command(self) -> None:
        seen = self.call("edit", "strong", "python3 -m unittest -q")
        argv = seen["argv"]
        self.assertEqual(self.values(argv, "--model"), ["opus"])
        self.assertEqual(seen["opus"], CONFIG["STRONG"])
        self.assertEqual(self.values(argv, "--tools"), ["Read,Glob,Grep,Edit,Write,Bash"])
        self.assertEqual(self.values(argv, "--allowedTools"),
                         ["Read(./**)", "Edit(./**)", "Bash(python3 -m unittest -q)"])
        sandbox = json.loads(self.values(argv, "--settings")[0])["sandbox"]
        # Probe 2026-09-24: with automatic approval of sandboxed commands left on,
        # the helper ran `cat ../outside.txt` although only the check was allowed.
        self.assertEqual((sandbox["enabled"], sandbox["autoAllowBashIfSandboxed"],
                          sandbox["allowUnsandboxedCommands"], sandbox["network"]["allowedDomains"]),
                         (True, False, False, []))

    def test_review_with_check_runs_tests_without_edit_rights(self) -> None:
        argv = self.call("review", "fast", "pnpm test")["argv"]
        self.assertEqual(self.values(argv, "--tools"), ["Read,Glob,Grep,Bash"])
        self.assertEqual(self.values(argv, "--allowedTools"), ["Read(./**)", "Bash(pnpm test)"])

    def test_bad_arguments_never_launch(self) -> None:
        paths = (str(self.project), str(self.prompt), str(self.output))
        for args in (("write", "fast", *paths), ("review", "huge", *paths),
                     ("review", "fast", "relative/dir", *paths[1:]), ("review", "fast", *paths, "x)"),
                     ("review", "fast", *paths[:2]), ("review", "fast", *paths[:2], paths[1])):
            with self.subTest(args=args[:3]):
                result = self.run_helper(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.output.exists())

    def test_tracing_never_prints_profile_values(self) -> None:
        result = self.run_helper("review", "fast", str(self.project), str(self.prompt), str(self.output), trace=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("s3cr3t-value", result.stderr)


if __name__ == "__main__":
    unittest.main()
