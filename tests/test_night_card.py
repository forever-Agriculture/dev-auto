# MODULE: test_night_card.py - departure composer behavior on exhausted and unknown facts
import importlib.util
from pathlib import Path
import unittest

module_path = Path(__file__).resolve().parents[1] / "skills/dev-auto/scripts/night_card.py"
spec = importlib.util.spec_from_file_location("night_card", module_path)
night = importlib.util.module_from_spec(spec)
spec.loader.exec_module(night)


class NightCardTest(unittest.TestCase):
    def setUp(self):
        self.facts = {
            "plan": {"state": "recorded", "limits": [
                {"name": "rechecks", "value": 4, "ceiling": 4, "per": "boundary", "mayRaise": False,
                 "boundaries": [{"boundary": "7.2", "used": 4, "left": 0}, {"boundary": "7.3", "used": 0, "left": 4}]}]},
            "pullRequests": {"state": "read", "items": [
                {"repository": "example/app", "number": 1, "headSha": "a" * 40, "base": "main", "policy": "prs-only", "mayMerge": False}]},
            "conflicts": [{"id": "limit:rechecks:7.2"}, {"id": "pr:example/app:1"}],
        }

    def test_three_necessary_lines(self):
        remaining = {
            "title": "Epic Seven", "scope": "One check ahead",
            "limits": [{"name": "rechecks", "boundary": "7.2", "uses": 2, "reason": "Two rechecks remain"},
                       {"name": "rechecks", "boundary": "7.3", "uses": 1, "reason": "One more boundary"}],
            "access": [{"name": "Fixture login", "command": "fixture auth login", "reason": "The check failed"}],
        }
        card = night.compose(self.facts, remaining, "/checkout", 7)
        self.assertEqual([term["kind"] for term in card["terms"]], ["limit", "access", "merge"])
        self.assertEqual({key: card["terms"][0][key] for key in ("from", "to")}, {"from": 4, "to": 6})
        self.assertEqual(card["terms"][2]["headSha"], "a" * 40)

    def test_epic_limit_combines_needs_across_boundaries(self):
        self.facts["plan"]["limits"].append(
            {"name": "consults", "value": 4, "ceiling": 4, "per": "epic", "mayRaise": False, "used": 3, "left": 1})
        remaining = {"title": "Epic Seven", "scope": "Two pending boundaries", "limits": [
            {"name": "consults", "boundary": "7.2", "uses": 1, "reason": "A storage decision"},
            {"name": "consults", "boundary": "7.3", "uses": 1, "reason": "An authority decision"},
        ]}
        [raise_term, _merge_term] = night.compose(self.facts, remaining, "/checkout", 7)["terms"]
        self.assertEqual(raise_term["to"], 5)
        self.assertEqual(raise_term["reason"], "A storage decision · An authority decision")

    def test_ceiling_and_empty_acknowledgment(self):
        self.facts["pullRequests"]["items"][0]["policy"] = "merge-when-green"
        remaining = {"title": "Epic Seven", "scope": "One check ahead", "nothing_reason": "No further review uses."}
        with self.assertRaisesRegex(ValueError, "Explain each conflict"):
            night.compose(self.facts, remaining, "/checkout", 7)
        remaining["despite"] = [item["id"] for item in self.facts["conflicts"]]
        self.assertTrue(night.compose(self.facts, remaining, "/checkout", 7)["nothing"])
        self.facts["plan"]["state"] = "unknown"
        with self.assertRaisesRegex(ValueError, "could not confirm"):
            night.compose(self.facts, remaining, "/checkout", 7)

    def test_asks_only_when_projected_need_exceeds_ceiling(self):
        limit = self.facts["plan"]["limits"][0]
        limit.update(value=3, ceiling=4, mayRaise=True)
        limit["boundaries"][0].update(used=3)
        need = {"name": "rechecks", "boundary": "7.2", "uses": 1, "reason": "More review work"}
        remaining = {"title": "Epic Seven", "scope": "Upcoming review", "limits": [need]}
        self.assertEqual([term["kind"] for term in night.compose(self.facts, remaining, "/checkout", 7)["terms"]], ["merge"])
        need["uses"] = 3
        term = night.compose(self.facts, remaining, "/checkout", 7)["terms"][0]
        self.assertEqual((term["from"], term["to"]), (3, 6))
