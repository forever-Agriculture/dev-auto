# MODULE: test_luna_browse.py - offline checks of the Luna browser-check wrapper's limits
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "dev-auto" / "scripts" / "luna-browse.sh"
FAKE_CODEX = """#!/usr/bin/env python3
import json, sys
argv = sys.argv[1:]
out = argv[argv.index("-o") + 1]
open(out, "w").write(json.dumps({"argv": argv, "stdin": sys.stdin.read()}))
"""
BROWSING = {"navigate", "navigate_back", "snapshot", "click", "type", "fill_form", "select_option",
            "press_key", "hover", "wait_for", "take_screenshot", "console_messages",
            "network_requests", "close"}


class LunaBrowseTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "bin").mkdir()
        codex = root / "bin" / "codex"
        codex.write_text(FAKE_CODEX)
        codex.chmod(0o755)
        self.project = root / "project"
        self.project.mkdir()
        self.prompt = root / "prompt.md"
        self.prompt.write_text("check the page")
        self.output = root / "out.json"
        self.env = {**os.environ, "PATH": f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}"}

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["bash", str(SCRIPT), *args], env=self.env, capture_output=True,
                              text=True, timeout=30)

    def call(self, origin: str) -> list[str]:
        result = self.run_script(str(self.project), str(self.prompt), str(self.output), origin)
        self.assertEqual(result.returncode, 0, result.stderr)
        seen = json.loads(self.output.read_text())
        self.assertEqual(seen["stdin"], "check the page")
        return seen["argv"]

    @staticmethod
    def configs(argv: list[str]) -> dict:
        merged: dict = {}
        for i, arg in enumerate(argv):
            if arg == "-c":  # Codex reads a bare word such as `max` as a string, as TOML does not
                key, value = argv[i + 1].split("=", 1)
                try:
                    merged.update(tomllib.loads(argv[i + 1]))
                except tomllib.TOMLDecodeError:
                    merged[key] = value
        return merged

    def test_luna_read_only_with_exactly_the_browser_tools(self) -> None:
        origin = "http://127.0.0.1:4173"
        argv = self.call(origin)
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-luna")
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
        self.assertEqual(argv[argv.index("-C") + 1], str(self.project))
        config = self.configs(argv)
        self.assertEqual((config["model_reasoning_effort"], config["approval_policy"]), ("max", "never"))
        self.assertEqual(list(config["mcp_servers"]), ["playwright"])
        server = config["mcp_servers"]["playwright"]
        self.assertEqual(server["command"], "npx")
        self.assertNotIn("url", server)  # a remote MCP server would bypass the loopback limit
        args = server["args"]
        self.assertEqual(args[args.index("--allowed-origins") + 1], origin)
        self.assertTrue({"--headless", "--isolated", "--offline"} <= set(args))
        # Exactly the named tools: an evaluate/run_code or file_upload tool widens what a page reaches.
        self.assertEqual(sorted(server["enabled_tools"]), sorted(f"browser_{t}" for t in BROWSING))
        self.assertEqual(server["default_tools_approval_mode"], "approve")

    def test_every_loopback_spelling_is_accepted(self) -> None:
        for index, origin in enumerate(("http://[::1]:8080", "http://localhost:80",
                                        "http://127.0.0.1:1", "http://127.0.0.1:65535")):
            with self.subTest(origin=origin):
                self.output = self.output.with_name(f"origin-{index}.json")
                server = self.configs(self.call(origin))["mcp_servers"]["playwright"]
                self.assertEqual(server["args"][server["args"].index("--allowed-origins") + 1], origin)

    def test_bad_origins_and_arguments_never_launch(self) -> None:
        paths = (str(self.project), str(self.prompt), str(self.output))
        for origin in ("https://127.0.0.1:3000", "http://example.com:80", "http://127.0.0.1",
                       'http://127.0.0.1:3000"]}}', "http://10.0.0.1:3000", "http://127.0.0.1:3000/",
                       "http://127.0.0.1:0", "http://127.0.0.1:65536", "http://0.0.0.0:3000"):
            with self.subTest(origin=origin):
                self.assertEqual(self.run_script(*paths, origin).returncode, 2)
                self.assertFalse(self.output.exists(), "provider was launched")
        for args in (paths, ("relative", *paths[1:], "http://127.0.0.1:3000"),
                     (*paths, "http://127.0.0.1:3000", "extra")):
            with self.subTest(args=args):
                self.assertEqual(self.run_script(*args).returncode, 2)
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
