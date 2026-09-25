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

    def test_edit_scopes_edits_without_shell_execution(self) -> None:
        seen = self.call("edit", "strong")
        argv = seen["argv"]
        self.assertEqual(self.values(argv, "--model"), ["opus"])
        self.assertEqual(seen["opus"], CONFIG["STRONG"])
        self.assertEqual(self.values(argv, "--tools"), ["Read,Glob,Grep,Edit,Write"])
        self.assertEqual(self.values(argv, "--allowedTools"),
                         ["Read(./**)", "Edit(./**)"])
        self.assertNotIn("--settings", argv)

    def test_browse_drives_only_the_loopback_origin(self) -> None:
        origin = "http://127.0.0.1:4173"
        argv = self.call("browse", "fast", origin)["argv"]
        self.assertIn("--restricted", argv)
        self.assertNotIn("--safe-mode", argv)
        servers = json.loads(self.values(argv, "--mcp-config")[0])["mcpServers"]
        self.assertEqual(list(servers), ["playwright"])
        server = servers["playwright"]
        self.assertEqual(server["command"], "npx")
        self.assertNotIn("url", server)  # a remote MCP server would bypass the loopback limit
        args = server["args"]
        self.assertEqual(args.count("--allowed-origins"), 1)
        self.assertEqual(args[args.index("--allowed-origins") + 1], origin)
        # --offline only resolves a pinned version; a bare @playwright/mcp would hit the network.
        self.assertTrue({"--headless", "--isolated", "--offline"} <= set(args))
        self.assertTrue([arg for arg in args if arg.startswith("@playwright/mcp@")], args)

    def test_browse_needs_a_loopback_origin(self) -> None:
        paths = (str(self.project), str(self.prompt), str(self.output))
        for origin in ("https://127.0.0.1:3000", "http://example.com:80", "http://127.0.0.1",
                       "http://127.0.0.1:3000/app", 'http://127.0.0.1:3000"]}}', "http://10.0.0.1:3000",
                       "HTTP://127.0.0.1:3000", "http://LOCALHOST:3000", "http://127.0.0.1:3000/",
                       " http://127.0.0.1:3000", "http://127.0.0.1:3000\t", "http://127.0.0.1:",
                       "http://127.0.0.1:0", "http://127.0.0.1:0300", "http://127.0.0.1:65536",
                       "http://127.0.0.1:123456", "http://0.0.0.0:3000", "http://127.0.0.2:3000"):
            with self.subTest(origin=origin):
                result = self.run_helper("browse", "fast", *paths, origin)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.output.exists(), "provider was launched")
        result = self.run_helper("browse", "fast", *paths)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(self.output.exists())

    def test_every_mode_passes_max_effort(self) -> None:
        # Effort must not depend on mode or tier: fast drafts reason as hard as strong ones.
        for mode, extra in (("review", ()), ("edit", ()), ("browse", ("http://127.0.0.1:3000",))):
            for tier in ("fast", "strong"):
                with self.subTest(mode=mode, tier=tier):
                    output = self.output.with_name(f"effort-{mode}-{tier}.json")
                    result = self.run_helper(mode, tier, str(self.project), str(self.prompt),
                                             str(output), *extra)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    argv = json.loads(output.read_text())["argv"]
                    self.assertEqual(argv.count("--effort"), 1)
                    self.assertEqual(self.values(argv, "--effort"), ["max"])

    def test_browse_accepts_every_loopback_host_spelling(self) -> None:
        # localhost and [::1] are loopback too; ports run 1-65535.
        for index, origin in enumerate(("http://[::1]:8080", "http://localhost:80",
                                        "http://127.0.0.1:1", "http://127.0.0.1:65535")):
            with self.subTest(origin=origin):
                output = self.output.with_name(f"origin-{index}.json")
                result = self.run_helper("browse", "strong", str(self.project), str(self.prompt),
                                         str(output), origin)
                self.assertEqual(result.returncode, 0, result.stderr)
                argv = json.loads(output.read_text())["argv"]
                config = json.loads(self.values(argv, "--mcp-config")[0])
                args = config["mcpServers"]["playwright"]["args"]
                self.assertEqual(args[args.index("--allowed-origins") + 1], origin)

    def test_browse_exposes_no_shell_edit_or_code_running_tools(self) -> None:
        argv = self.call("browse", "strong", "http://127.0.0.1:3000")["argv"]
        self.assertEqual(self.values(argv, "--tools"), ["Read,Glob,Grep"])
        allowed = self.values(argv, "--allowedTools")
        browsing = {"navigate", "navigate_back", "snapshot", "click", "type", "fill_form",
                    "select_option", "press_key", "hover", "wait_for", "take_screenshot",
                    "console_messages", "network_requests", "close"}
        # Exactly the named browser tools plus scoped Read: a wildcard or an added
        # evaluate/run_code style tool would widen what a hostile page could reach.
        self.assertEqual({tool for tool in allowed if tool != "Read(./**)"},
                         {f"mcp__playwright__browser_{tool}" for tool in browsing})
        self.assertEqual(len(allowed), len(set(allowed)))
        self.assertEqual(self.values(argv, "--disallowedTools"),
                         ["Read(./**/.env*)", "Edit(./**/.env*)"])

    def test_review_and_edit_keep_safe_mode_and_reject_the_origin_argument(self) -> None:
        for mode in ("review", "edit"):
            with self.subTest(mode=mode):
                output = self.output.with_name(f"safe-{mode}.json")
                result = self.run_helper(mode, "fast", str(self.project), str(self.prompt),
                                         str(output))
                self.assertEqual(result.returncode, 0, result.stderr)
                argv = json.loads(output.read_text())["argv"]
                self.assertIn("--safe-mode", argv)
                self.assertNotIn("--restricted", argv)
                self.assertEqual(json.loads(self.values(argv, "--mcp-config")[0]),
                                 {"mcpServers": {}})
                # browse's sixth argument must not silently widen the older modes.
                refused = self.output.with_name(f"safe-{mode}-origin.json")
                result = self.run_helper(mode, "fast", str(self.project), str(self.prompt),
                                         str(refused), "http://127.0.0.1:3000")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(refused.exists(), "provider was launched")

    def test_check_argument_rejected_before_provider_launch(self) -> None:
        # A live exact-command probe read ../outside.txt and an inherited environment
        # marker. Both modes must reject the old route, not silently ignore CHECK.
        for mode in ("review", "edit"):
            with self.subTest(mode=mode):
                output = self.output.with_name(f"{mode}-receipt.json")
                result = self.run_helper(mode, "fast", str(self.project), str(self.prompt),
                                         str(output), "python3 -m unittest -q")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(output.exists(), "provider was launched")

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
