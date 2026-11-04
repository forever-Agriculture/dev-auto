# MODULE: test_review_misses.py - BMN Epic 105.5: review facts per ticket, candidates never called misses, read-only and bounded, against a fake gh
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "dev-auto" / "scripts" / "review_misses.py"
RECORD = "Agent review (review-tools:review) at aaaaaaaaaaaa, final bbbbbbbbbbbb: 2 fixed, 1 not worth doing, 0 open.\n\nLenses: bugs."
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
data = json.load(open(os.environ["FAKE_GH_DATA"]))
time.sleep(float(data.get("delay", 0)))
if args[:2] == ["search", "prs"]:
    key = "reverts" if "Revert in:title" in args else "prs"
    if key == "prs" and data.get("search_fails"):
        print("boom", file=sys.stderr); sys.exit(1)
    print(json.dumps(data.get(key, [])))
elif args[:2] == ["search", "commits"]:
    print(json.dumps(data.get("commits", [])))
elif args[0] == "api":
    path = args[-1].split("?")[0]
    if path in data.get("fail", []):
        print("boom", file=sys.stderr); sys.exit(1)
    answer = data.get("api", {}).get(path, [])
    if isinstance(answer, dict):
        print(json.dumps(answer["page1"])); print(json.dumps(answer["page2"]))
    else:
        print(json.dumps(answer))
else:
    print("unexpected " + " ".join(args), file=sys.stderr); sys.exit(9)
"""


def pr(repo: str, number: int, title: str, state: str = "merged", labels: tuple[str, ...] = (), author: str = "owner-login") -> dict:
    return {"repository": {"nameWithOwner": repo}, "number": number, "title": title, "state": state, "url": f"https://github.com/{repo}/pull/{number}",
            "author": {"login": author}, "createdAt": "2026-10-25T10:00:00Z", "closedAt": "2026-10-26T10:00:00Z", "updatedAt": "2026-10-27T10:00:00Z",
            "labels": [{"name": name} for name in labels]}


def person_event(login: str, at: str, url: str, kind: str = "User") -> dict:
    return {"user": {"login": login, "type": kind}, "submitted_at": at, "created_at": at, "html_url": url}


class ReviewMissesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fake = self.root / "gh"
        fake.write_text(FAKE_GH)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.log = self.root / "gh.log"
        self.data = self.root / "data.json"
        self.lessons = self.root / "lessons.md"

    def run_it(self, data: dict, *extra: str) -> subprocess.CompletedProcess:
        self.data.write_text(json.dumps(data))
        env = {**os.environ, "PATH": f"{self.root}:{os.environ['PATH']}", "FAKE_GH_LOG": str(self.log), "FAKE_GH_DATA": str(self.data)}
        return subprocess.run([sys.executable, str(SCRIPT), "--owner", "example-org", "--since", "2026-10-23", "--lessons", str(self.lessons), *extra],
                              capture_output=True, text=True, env=env, timeout=60)

    def read_json(self, data: dict, *extra: str) -> dict:
        done = self.run_it(data, "--json", *extra)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def fixture(self) -> dict:
        a = "example-org/project-p.services.alpha"
        b = "example-org/project-p.website"
        return {
            "prs": [pr(a, 1, "T100 reviewed and caught"), pr(b, 2, "fix(T100): second half"), pr(a, 3, "T200 docs only"),
                    pr(a, 4, "No ticket here", labels=("release:blocked",)), pr(a, 5, "T300 not reviewed"), pr(a, 6, "T400 closed unmerged", state="closed"),
                    pr(a, 7, "T500 reverted", state="open"), pr(a, 9, "T600 label removed since"), pr(a, 10, "T700 blocked before the review")],
            "reverts": [{"repository": {"nameWithOwner": a}, "title": 'Revert "T500 reverted"', "body": f"Reverts {a}#7", "url": f"https://github.com/{a}/pull/8"}],
            "commits": [{"repository": {"fullName": a}, "commit": {"message": 'Revert "T500 reverted (#7)"\n\nThis reverts'}, "url": f"https://github.com/{a}/commit/abc"},
                        {"repository": {"fullName": a}, "commit": {"message": "Merge pull request #5 mentioning a revert"}, "url": f"https://github.com/{a}/commit/def"}],
            "api": {
                f"repos/{a}/pulls/1/files": {"page1": [{"filename": "a.py", "additions": 2, "patch": "@@ -1 +1,2 @@\n+# MODULE: a.py - banner\n+code\n # MODULE: context stays\n-# MODULE: removed"}],
                                             "page2": [{"filename": "b.cs", "additions": 1, "patch": "+#region MODULE: b.cs\n+// MODULE: b2"}, {"filename": "big.bin", "additions": 9}]},
                f"repos/{a}/issues/1/comments": [{"body": "unrelated", "created_at": "2026-10-25T11:00:00Z"},
                                                 {"body": RECORD, "created_at": "2026-10-25T12:00:00Z", "html_url": "https://example.invalid/record"}],
                f"repos/{a}/pulls/1/reviews": [{**person_event("dana", "2026-10-25T11:30:00Z", "https://example.invalid/before"), "state": "CHANGES_REQUESTED"},
                                               {**person_event("dana", "2026-10-25T13:00:00Z", "https://example.invalid/after"), "state": "CHANGES_REQUESTED"},
                                               {**person_event("dana", "2026-10-25T14:00:00Z", "https://example.invalid/approved"), "state": "APPROVED"},
                                               {**person_event("owner-login", "2026-10-25T15:00:00Z", "https://example.invalid/self"), "state": "CHANGES_REQUESTED"}],
                f"repos/{a}/pulls/1/comments": [person_event("dana", "2026-10-25T13:01:00Z", "https://example.invalid/line"),
                                                person_event("release-bot[bot]", "2026-10-25T13:02:00Z", "https://example.invalid/bot", "Bot"),
                                                person_event("owner-login", "2026-10-25T13:03:00Z", "https://example.invalid/own")],
                f"repos/{b}/pulls/2/files": [{"filename": "src/x.ts", "additions": 1, "patch": "+x"}],
                f"repos/{a}/pulls/3/files": [{"filename": "docs/a.txt", "additions": 1, "patch": "+# MODULE: d"}, {"filename": "README.md", "additions": 1, "patch": "+x"}],
                f"repos/{a}/pulls/4/files": [{"filename": "docs.py", "additions": 1, "patch": "+x"}],
                f"repos/{a}/pulls/5/files": [{"filename": "c.py", "additions": 1, "patch": "+x"}],
                f"repos/{a}/issues/5/comments": [{"body": "Agent review, sort of: looks fine", "created_at": "2026-10-25T12:00:00Z"}],
                f"repos/{a}/pulls/5/reviews": [{**person_event("dana", "2026-10-25T11:30:00Z", "https://example.invalid/unreviewed"), "state": "CHANGES_REQUESTED"}],
                f"repos/{a}/pulls/7/files": [{"filename": "e.py", "additions": 1, "patch": "+x"}],
                f"repos/{a}/pulls/9/files": [{"filename": "f.py", "additions": 1, "patch": "+x"}],
                f"repos/{a}/issues/9/events": [{"event": "labeled", "label": {"name": "release:ready"}, "created_at": "2026-10-25T10:00:00Z"},
                                               {"event": "labeled", "label": {"name": "release:blocked"}, "created_at": "2026-10-26T10:00:00Z"},
                                               {"event": "unlabeled", "label": {"name": "release:blocked"}, "created_at": "2026-10-27T10:00:00Z"}],
                f"repos/{a}/pulls/10/files": [{"filename": "g.py", "additions": 1, "patch": "+x"}],
                f"repos/{a}/issues/10/comments": [{"body": RECORD, "created_at": "2026-10-26T12:00:00Z", "html_url": "https://example.invalid/record10"}],
                f"repos/{a}/issues/10/events": [{"event": "labeled", "label": {"name": "release:blocked"}, "created_at": "2026-10-26T10:00:00Z"}],
            },
        }

    def by_key(self, result: dict) -> dict:
        return {(pr["repo"].split("/")[-1], pr["number"]): pr for group in result["groups"] for pr in group["prs"]}

    def test_groups_by_ticket_else_alone_and_skips_closed_unmerged(self) -> None:
        result = self.read_json(self.fixture())
        names = {group["group"]: [pr["number"] for pr in group["prs"]] for group in result["groups"]}
        self.assertEqual(names, {"T100": [1, 2], "T200": [3], "example-org/project-p.services.alpha#4": [4], "T300": [5], "T500": [7], "T600": [9], "T700": [10]})

    def test_eligibility_is_one_function_and_plan_is_exempt(self) -> None:
        spec = importlib.util.spec_from_file_location("review_misses", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        eligible = module.review_eligible
        self.assertFalse(eligible(["plan/status.yaml", "plan/epics/001-x.md"]), "plan only")
        self.assertFalse(eligible(["README.md", "docs/a.txt", "plan/references/x.json"]), "all exempt, each for its own reason")
        self.assertTrue(eligible(["plan/status.yaml", "src/a.py"]), "mixed")
        self.assertTrue(eligible(["src/a.py"]), "code")
        self.assertTrue(eligible(["planning/a.py", "src/plan/a.py"]), "only the top plan folder")
        self.assertTrue(eligible([]), "an unread file list is never exempt")

    def test_docs_only_is_all_md_or_under_docs(self) -> None:
        prs = self.by_key(self.read_json(self.fixture()))
        self.assertTrue(prs[("project-p.services.alpha", 3)]["docs_only"])
        self.assertFalse(prs[("project-p.services.alpha", 3)]["eligible"])
        self.assertFalse(prs[("project-p.services.alpha", 4)]["docs_only"], "docs.py is not under docs/")

    def test_only_the_record_comment_makes_it_reviewed(self) -> None:
        prs = self.by_key(self.read_json(self.fixture()))
        one = prs[("project-p.services.alpha", 1)]
        self.assertEqual((one["reviewed"], one["reviewed_head"], one["final_head"]), (True, "aaaaaaaaaaaa", "bbbbbbbbbbbb"))
        five = prs[("project-p.services.alpha", 5)]
        self.assertEqual((five["reviewed"], five["reviewed_head"]), (False, None), "a look-alike comment is not the record")

    def test_later_events_are_by_people_after_the_comment_with_links(self) -> None:
        prs = self.by_key(self.read_json(self.fixture()))
        events = prs[("project-p.services.alpha", 1)]["events"]
        self.assertEqual([(event["kind"], event["url"]) for event in events],
                         [("changes-requested", "https://example.invalid/after"), ("line-comment", "https://example.invalid/line")])

    def test_a_pull_request_with_no_record_lists_all_its_events(self) -> None:
        prs = self.by_key(self.read_json(self.fixture()))
        self.assertEqual([event["url"] for event in prs[("project-p.services.alpha", 5)]["events"]], ["https://example.invalid/unreviewed"])

    def test_release_blocked_and_a_revert_are_candidates_and_a_revert_counts_once(self) -> None:
        prs = self.by_key(self.read_json(self.fixture()))
        self.assertEqual([event["kind"] for event in prs[("project-p.services.alpha", 4)]["events"]], ["release:blocked"])
        reverted = prs[("project-p.services.alpha", 7)]["events"]
        self.assertEqual([event["kind"] for event in reverted], ["revert"])
        self.assertEqual(prs[("project-p.services.alpha", 5)]["events"][0]["kind"], "changes-requested", "a merge commit mentioning #5 is no revert")

    def test_a_block_label_removed_since_still_counts_and_one_before_the_review_does_not(self) -> None:
        prs = self.by_key(self.read_json(self.fixture()))
        self.assertEqual([(event["kind"], event["at"]) for event in prs[("project-p.services.alpha", 9)]["events"]], [("release:blocked", "2026-10-26T10:00:00Z")])
        self.assertEqual(prs[("project-p.services.alpha", 10)]["events"], [])

    def test_banner_lines_added_across_pages_and_a_patch_too_large_is_named(self) -> None:
        prs = self.by_key(self.read_json(self.fixture()))
        one = prs[("project-p.services.alpha", 1)]
        self.assertEqual(one["banner_lines"], 3, "added only: # MODULE, #region MODULE, // MODULE")
        self.assertEqual(one["unread_patches"], 1)

    def test_totals_read_as_the_story_says(self) -> None:
        totals = self.read_json(self.fixture())["totals"]
        self.assertEqual(totals, {"groups": 7, "eligible": 7, "reviewed": 2, "candidates": 6, "banners_added": 4, "confirmed_misses": 0})

    def test_only_an_escape_line_naming_a_listed_pull_request_confirms_a_miss(self) -> None:
        self.lessons.write_text("escape: missed x, see y https://github.com/example-org/project-p.services.alpha/pull/1\n"
                                "history: old finding https://github.com/example-org/project-p.services.alpha/pull/5\n"
                                "escape: not listed https://github.com/example-org/project-p.services.alpha/pull/999\n"
                                "- escape: not at the start https://github.com/example-org/project-p.services.alpha/pull/5\n")
        result = self.read_json(self.fixture())
        self.assertEqual(result["totals"]["confirmed_misses"], 1)
        self.assertIn("pull/1", result["confirmed"][0])

    def test_text_calls_events_candidates_never_misses(self) -> None:
        done = self.run_it(self.fixture())
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("candidate: changes-requested dana https://example.invalid/after", done.stdout)
        self.assertIn("Totals: groups 7, eligible 7, reviewed 2, candidates 6, banners added 4, confirmed misses 0.", done.stdout)
        self.assertIn("eligible, not reviewed", done.stdout)
        self.assertIn("docs-only, skipped", done.stdout)
        self.assertIn("Covered: example-org/project-p.services.alpha, example-org/project-p.website.", done.stdout)
        self.assertNotIn("miss:", done.stdout.lower())

    def test_author_goes_to_the_search_and_every_call_only_reads(self) -> None:
        self.run_it(self.fixture(), "--author", "owner-login")
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        pr_search = next(call for call in calls if call[:2] == ["search", "prs"] and "Revert in:title" not in call)
        self.assertEqual(pr_search[pr_search.index("--author") + 1], "owner-login")
        self.assertTrue(calls)
        for call in calls:
            self.assertIn(call[0], ("search", "api"))
            self.assertNotIn("--method", call)
            self.assertNotIn("-X", call)
            self.assertNotIn("-f", call)
            self.assertNotIn("--input", call)

    def test_out_of_time_stops_and_names_what_it_did_not_cover(self) -> None:
        data = self.fixture()
        data["delay"] = 0.6
        started = time.monotonic()
        result = self.read_json(data, "--seconds", "1")
        self.assertLess(time.monotonic() - started, 8)
        self.assertTrue(result["coverage"]["not_covered"], result["coverage"])
        self.assertTrue(result["coverage"]["gaps"])

    def test_a_failed_read_names_its_repository_and_the_rest_is_kept(self) -> None:
        data = self.fixture()
        data["fail"] = ["repos/example-org/project-p.website/pulls/2/files"]
        result = self.read_json(data)
        self.assertEqual(result["coverage"]["not_covered"], ["example-org/project-p.website"])
        self.assertEqual(result["coverage"]["covered"], ["example-org/project-p.services.alpha"])
        self.assertTrue(any("project-p.website#2" in gap for gap in result["coverage"]["gaps"]))

    def test_a_failed_search_covers_nothing_and_says_so(self) -> None:
        result = self.read_json({"search_fails": True})
        self.assertEqual(result["coverage"]["covered"], [])
        self.assertEqual(result["coverage"]["not_covered"], ["example-org"])
        self.assertEqual(result["totals"]["groups"], 0)

    def test_usage_needs_owner_and_a_date(self) -> None:
        env = {**os.environ, "PATH": f"{self.root}:{os.environ['PATH']}"}
        for args in ([], ["--owner", "example-org"], ["--owner", "example-org", "--since", "yesterday"]):
            done = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)
            self.assertEqual(done.returncode, 2, args)


if __name__ == "__main__":
    unittest.main()
