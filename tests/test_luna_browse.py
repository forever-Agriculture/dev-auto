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
# The team check: records what it was asked and answers as BMN_FAKE_VERDICT says.
FAKE_BMN = """#!/usr/bin/env python3
import json, os, sys
open(os.environ["BMN_FAKE_LOG"], "w").write(json.dumps(sys.argv[1:]))
refused = os.environ.get("BMN_FAKE_VERDICT") == "REFUSED"
print(json.dumps({"verdict": "REFUSED", "code": "PROPOSED"} if refused else {"verdict": "PASS"}))
sys.exit(10 if refused else 0)
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
        bmn = root / "bin" / "bmn"
        bmn.write_text(FAKE_BMN)
        bmn.chmod(0o755)
        self.checked = root / "bmn-argv.json"
        self.project = root / "project"
        self.project.mkdir()
        self.prompt = root / "prompt.md"
        self.prompt.write_text("check the page")
        self.output = root / "out.json"
        self.env = {**os.environ, "PATH": f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}",
                    "BMN_FAKE_LOG": str(self.checked)}

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        # Started from the repository, as a lead standing outside the project would.
        return subprocess.run(["bash", str(SCRIPT), *args], env=self.env, capture_output=True,
                              text=True, timeout=30, cwd=REPO)

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

    def test_the_team_check_sees_the_exact_command_before_it_runs(self) -> None:
        argv = self.call("http://127.0.0.1:4173")
        asked = json.loads(self.checked.read_text())
        split = asked.index("--")
        options = asked[:split]
        self.assertEqual(options[:2], ["roster", "check"])
        for flag, value in (("--agent", "luna"), ("--role", "browser"), ("--workspace", str(self.project)),
                            ("--data", "private"), ("--stdin", str(self.prompt)),
                            # The check refuses a folder outside the workspace: the run stands in the project.
                            ("--cwd", str(self.project))):
            self.assertEqual(options[options.index(flag) + 1], value)
        self.assertEqual(asked[split + 1:], ["codex", *argv])
        # The receipt stays beside the answer.
        self.assertEqual(json.loads(Path(f"{self.output}.check.json").read_text())["verdict"], "PASS")

    def test_a_refused_check_launches_nothing(self) -> None:
        self.env["BMN_FAKE_VERDICT"] = "REFUSED"
        result = self.run_script(str(self.project), str(self.prompt), str(self.output), "http://127.0.0.1:4173")
        self.assertEqual(result.returncode, 10)
        self.assertIn("PROPOSED", result.stderr)
        self.assertFalse(self.output.exists(), "provider was launched")

    def test_an_earlier_check_answer_is_kept(self) -> None:
        receipt = Path(f"{self.output}.check.json")
        receipt.write_text("earlier")
        result = self.run_script(str(self.project), str(self.prompt), str(self.output), "http://127.0.0.1:4173")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(receipt.read_text(), "earlier")
        self.assertFalse(self.output.exists(), "provider was launched")
        self.assertFalse(self.checked.exists(), "the check ran")

    def test_the_lead_may_name_another_effort_the_team_lists(self) -> None:
        result = self.run_script(str(self.project), str(self.prompt), str(self.output), "http://127.0.0.1:4173", "xhigh")
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = json.loads(self.output.read_text())["argv"]
        self.assertEqual(self.configs(argv)["model_reasoning_effort"], "xhigh")
        asked = json.loads(self.checked.read_text())
        self.assertEqual(asked[asked.index("--") + 1:], ["codex", *argv])

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
