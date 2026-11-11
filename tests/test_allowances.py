# MODULE: test_allowances.py - BMN Stories 110.4 and 110.6: an epic's allowances file through run_needs.py and spend_ledger.py; BMN's reader is a stub here (its own tests hold it)
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "dev-auto" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_needs  # noqa: E402
sys.path.insert(0, str(REPO / "tests"))
import test_run_needs  # noqa: E402

LEDGER = SCRIPTS / "spend_ledger.py"
STUB = """#!/bin/sh
if [ "$1 $2" = "plan allowances" ]; then cat "{root}/allowances.json"; exit 0; fi
cat "{root}/status.json"
"""
FILE = "schema: 1\nepic: 7\nlimits:\n  rechecks: {limit: 2, ceiling: 4, per: boundary}\n"
POINTER = "What this epic may use is in `plan/allowances/007.yaml`.\n"


def fields(rounds: float = 2, money: float | None = None, rechecks: dict | None = None, **rest: object) -> dict:
    limits = {"rechecks": rechecks or {"limit": 2, "ceiling": 4, "per": "boundary", "unit": "count"},
              "qa_passes": {"limit": 1, "per": "epic", "unit": "count"},
              "test_hours": {"limit": 1.5, "ceiling": 3, "per": "epic", "unit": "hours"}}
    return {"rounds": rounds, "deferrable": [], "money_cap": money, "named_actions": None, "prepared": [], "messages": [], "limits": limits, "may": [], "stays_out": [], **rest}


class Allowances(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "bin").mkdir()
        stub = self.root / "bin" / "bmn"
        stub.write_text(STUB.format(root=self.root))
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        patcher = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "state"), "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.plan = test_run_needs.Plan()
        self.addCleanup(self.plan.tmp.cleanup)
        self.body = test_run_needs.epic(POINTER)

    def message(self, allowances: str | None = FILE, date: str = "2026-10-23") -> str:
        approved = "sha256:" + run_needs.approval_text(run_needs.sections(self.body), allowances)
        return (f"plan: go for Epic 7 (go {date})\n\nGo-Epic: 7\nGo-Date: {date}\nApproval-Source: card {date}T09:00Z: 'Go'\n"
                f"Approved-Text: {approved}\nApproved-File: epics/007-fixture.md\n")

    def go(self, text: str | None = FILE, date: str = "2026-10-23") -> str:
        """A go on the epic, its commit holding `text` as the file; a later go of the same day is a new go by its commit."""
        folder = self.plan.root / "allowances"
        folder.mkdir(exist_ok=True)
        if text is None:
            (folder / "007.yaml").unlink(missing_ok=True)
        else:
            (folder / "007.yaml").write_text(text)
        self.plan.write("epic-7: backlog", self.body)
        commit = self.plan.write(f"epic-7: ready # go {date}", commit=self.message(text, date))
        self.write_status()
        return commit

    def write_status(self) -> None:
        (self.root / "status.json").write_text(json.dumps(self.plan.status()))

    def reader(self, values: dict, state: str = "recorded", hand_edit: str | None = None, commit: str | None = None, go_values: dict | None = None) -> None:
        commit = commit or "c" * 40
        (self.root / "allowances.json").write_text(json.dumps({
            "ok": True, "epic": 7, "file": "allowances/007.yaml", "state": state, "reason": "held" if state != "recorded" else None, "go_commit": commit, "token": "tok1", "hand_edit": hand_edit, "changes": [],
            "at_go": {"commit": commit, "fields": go_values or values, "text": FILE},
            "current": {"commit": commit, "source": "go", "text": FILE, "fields": values}}))

    def ledger(self, *argv: str) -> tuple[int, str]:
        done = subprocess.run([sys.executable, str(LEDGER), *argv], capture_output=True, text=True, env=os.environ.copy(), cwd=self.root)
        return done.returncode, done.stdout + done.stderr

    def open(self) -> str:
        code, out = self.ledger("open", "--epic", "7", "--project", str(self.plan.root))
        self.assertEqual(code, 0, out)
        self.opened = out
        return out.split()[1].rstrip(":")

    def data(self, budget: str) -> dict:
        return json.loads((self.root / "state" / "dev-auto" / "budgets" / f"{budget}.json").read_text())

    def use(self, budget: str, use_id: str, *rest: str, limit: str = "rechecks", boundary: str = "7.1") -> tuple[int, str]:
        return self.ledger("use", "--budget", budget, "--limit", limit, "--boundary", boundary, "--use-id", use_id, *rest)

    # 110.4

    def test_the_go_hashes_the_file_and_reads_it_through_bmn(self) -> None:
        self.go()
        self.reader(fields())
        found = self.plan.read()
        self.assertEqual(found["state"], "GO")
        self.assertEqual(found["provenance"], "recorded")
        self.assertEqual(found["approved_text"], "sha256:" + run_needs.approval_text(run_needs.sections(self.body), FILE))
        self.assertNotEqual(found["approved_text"], "sha256:" + run_needs.approval_text(run_needs.sections(self.body)))
        self.assertEqual(found["parsed"]["limits"]["rechecks"]["limit"], 2)
        self.assertEqual(found["allowances"]["token"], "tok1")

    def test_an_epic_with_no_file_reads_as_before(self) -> None:
        self.body = test_run_needs.epic()
        self.go(None)
        (self.root / "allowances.json").write_text("not read")
        found = self.plan.read()
        self.assertEqual(found["state"], "GO")
        self.assertEqual(found["approved_text"], "sha256:" + run_needs.approval_text(run_needs.sections(self.body)))
        self.assertNotIn("allowances", found)
        self.assertEqual(found["parsed"]["rounds"], 2)
        self.assertEqual(found["parsed"]["money_cap"], 15.0)

    def test_a_file_the_goes_commit_does_not_hold_grants_nothing_and_is_named(self) -> None:
        self.body = test_run_needs.epic()
        self.go(None)
        (self.plan.root / "allowances" / "007.yaml").write_text(FILE)
        found = self.plan.read()
        self.assertEqual(found["state"], "GO")
        self.assertEqual(found["parsed"]["rounds"], 2)
        self.assertIn("Allowances", found["changed_since_go"])

    def test_an_edited_go_file_fails_its_hash(self) -> None:
        self.go()
        self.reader(fields())
        (self.plan.root / "allowances" / "007.yaml").write_text(FILE.replace("limit: 2", "limit: 3"))
        self.plan.git("add", "-A")
        self.plan.git("commit", "-q", "--amend", "--no-edit")
        found = self.plan.read()
        self.assertEqual((found["state"], found["provenance"]), ("NO_GO_RECORD", "incomplete"))

    def test_a_reader_that_will_not_grant_grants_nothing(self) -> None:
        self.go()
        for state in ("withdrawn", "conflict", "invalid"):
            self.reader(fields(), state=state)
            found = self.plan.read()
            self.assertEqual(found["state"], "NO_GO_RECORD", state)
            self.assertTrue(found["unconfirmed"], state)
        (self.root / "allowances.json").write_text("{broken")
        self.assertTrue(self.plan.read()["unconfirmed"])

    def test_a_hand_edit_is_named_and_the_recorded_version_holds(self) -> None:
        self.go()
        self.reader(fields(), hand_edit="the working file differs from the last recorded version")
        found = self.plan.read()
        self.assertEqual(found["state"], "GO")
        self.assertIn("Allowances", found["changed_since_go"])
        self.assertEqual(found["parsed"]["limits"]["rechecks"]["limit"], 2)

    def test_it_prints_the_limits(self) -> None:
        self.go()
        self.reader(fields(may=["one run"], stays_out=["production"]))
        done = subprocess.run([sys.executable, str(SCRIPTS / "run_needs.py"), "7", "--project", str(self.plan.root)], capture_output=True, text=True, env=os.environ.copy())
        self.assertIn("ALLOWANCES: allowances/007.yaml", done.stdout)
        self.assertIn("- rechecks: 2 per boundary, ceiling 4", done.stdout)
        self.assertIn("- test_hours: 1.5 per epic, ceiling 3, hours", done.stdout)
        self.assertIn("MAY: one run", done.stdout)
        self.assertIn("STAYS OUT: production", done.stdout)

    # 110.6 AC1: use

    def test_use_counts_against_the_value_read_each_time_and_a_retry_returns_the_first_answer(self) -> None:
        self.go()
        self.reader(fields())
        budget = self.open()
        self.assertIn("LIMIT rechecks: 2 per boundary, ceiling 4", self.opened)
        self.assertEqual(self.use(budget, "a")[0], 0)
        code, out = self.use(budget, "a")
        self.assertEqual(code, 0)
        self.assertIn("nothing counted again", out)
        self.assertEqual(self.use(budget, "b")[0], 0)
        code, out = self.use(budget, "c")
        self.assertEqual(code, 1)
        self.assertIn("RAISE: room under its ceiling 4", out)
        self.assertIn("bmn plan allow 7 limits.rechecks.limit=3", out)
        self.assertIn("--expect tok1", out)
        # A raise takes effect with no restart; the same id keeps its first answer.
        self.reader(fields(rechecks={"limit": 3, "ceiling": 4, "per": "boundary", "unit": "count"}))
        self.assertEqual(self.use(budget, "c")[0], 1)
        code, out = self.use(budget, "d")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.data(budget)["uses"]["d"]["value"], 3)
        # Another boundary has its own count.
        self.assertEqual(self.use(budget, "e", boundary="epic")[0], 0)

    def test_at_the_ceiling_it_says_park_and_a_limit_per_epic_counts_across_boundaries(self) -> None:
        self.go()
        self.reader(fields())
        budget = self.open()
        self.assertEqual(self.use(budget, "a", limit="qa_passes")[0], 0)
        code, out = self.use(budget, "b", limit="qa_passes", boundary="epic")
        self.assertEqual(code, 1)
        self.assertIn("AT_CEILING", out)
        self.reader(fields(rechecks={"limit": 4, "ceiling": 4, "per": "boundary", "unit": "count"}))
        for n in range(4):
            self.assertEqual(self.use(budget, f"r{n}")[0], 0)
        code, out = self.use(budget, "r5")
        self.assertEqual(code, 1)
        self.assertIn("at its ceiling", out)
        self.assertIn("AT_CEILING", out)
        self.assertIn("OWNER_CHANGE", out)
        self.assertNotIn("only if the epic says so", out)
        self.assertEqual(self.data(budget)["uses"]["r5"]["answer"], "REFUSED")
        # Advice to request an amendment cannot grant a use or refill earlier ones.
        self.assertEqual(self.use(budget, "r5")[0], 1)

    def test_hours_are_decimals_and_a_count_is_whole(self) -> None:
        self.go()
        self.reader(fields())
        budget = self.open()
        self.assertEqual(self.use(budget, "a", "--amount", "0.5", limit="test_hours")[0], 0)
        self.assertEqual(self.use(budget, "b", "--amount", "1", limit="test_hours")[0], 0)
        code, out = self.use(budget, "c", "--amount", "0.25", limit="test_hours")
        self.assertEqual(code, 1, out)
        self.assertIn("limits.test_hours.limit=1.75", out)
        self.assertEqual(self.use(budget, "d", "--amount", "1.5")[0], 2)
        self.assertEqual(self.use(budget, "e", "--amount", "0")[0], 2)

    def test_use_refuses_a_limit_counted_elsewhere_an_unknown_one_and_a_boundary_outside_the_epic(self) -> None:
        self.go()
        self.reader(fields())
        budget = self.open()
        self.assertEqual(self.use(budget, "a", limit="repair_rounds")[0], 2)
        self.assertEqual(self.use(budget, "b", limit="money_usd")[0], 2)
        code, out = self.use(budget, "c", limit="pages")
        self.assertEqual(code, 1)
        self.assertIn("names no limit pages", out)
        self.assertEqual(self.use(budget, "d", boundary="8.1")[0], 2)
        self.assertEqual(self.use(budget, "e", boundary="7.9")[0], 2)

    def test_a_refused_use_id_stays_refused_after_the_reason_goes_away(self) -> None:
        # Full review: the first answer holds for a refusal too; only a fresh id may count once the limit exists.
        self.go()
        self.reader(fields())
        budget = self.open()
        code, out = self.use(budget, "same-id", limit="pages")
        self.assertEqual(code, 1, out)
        self.assertIn("names no limit pages", out)
        self.reader(fields() | {"limits": {**fields()["limits"], "pages": {"limit": 3, "per": "epic", "unit": "count"}}})
        code, out = self.use(budget, "same-id", limit="pages")
        self.assertEqual(code, 1, out)
        self.assertIn("was answered first", out)
        self.assertEqual(self.use(budget, "fresh-id", limit="pages")[0], 0)
        code, out = self.ledger("status", "--budget", budget)
        self.assertEqual(code, 0, out)
        self.assertIn("use same-id: REFUSED pages", out)

    def test_use_defaults_with_no_file_but_refuses_a_withdrawn_go(self) -> None:
        self.body = test_run_needs.epic()
        self.go(None)
        budget = self.open()
        code, out = self.use(budget, "a")
        self.assertEqual(code, 0, out)
        self.assertIn("DEFAULT: rechecks: 4 per boundary", out)
        self.body = test_run_needs.epic(POINTER)
        self.go(FILE, "2026-10-24")
        self.reader(fields())
        budget = self.open()
        self.assertEqual(self.use(budget, "b")[0], 0)
        self.plan.write("epic-7: backlog")
        code, out = self.use(budget, "c")
        self.assertEqual(code, 1)
        self.assertIn("was withdrawn", out)

    def test_default_names_never_fill_a_gap_in_an_approved_file(self) -> None:
        self.go()
        self.reader(fields())
        budget = self.open()
        code, out = self.use(budget, "no-consult", limit="consults")
        self.assertEqual(code, 1, out)
        self.assertIn("file names no limit consults", out)
        self.assertNotIn("DEFAULT:", out)
        values = fields()
        values["limits"].update({"consults": {"limit": 1, "per": "epic"},
                                 "senior_consults": {"limit": 0, "per": "epic"},
                                 "full_reviews": {"limit": 1, "ceiling": 2, "per": "boundary"}})
        self.reader(values)
        self.assertEqual(self.use(budget, "consult", limit="consults")[0], 0)
        self.assertEqual(self.use(budget, "consult-over", limit="consults")[0], 1)
        self.assertEqual(self.use(budget, "senior-zero", limit="senior_consults")[0], 1)
        self.assertEqual(self.use(budget, "full", limit="full_reviews")[0], 0)
        code, out = self.use(budget, "full-over", limit="full_reviews")
        self.assertEqual(code, 1, out)
        self.assertIn("RAISE: room under its ceiling 2", out)
        self.reader(values, state="invalid")
        self.assertEqual(self.use(budget, "invalid-consult", limit="consults")[0], 1)

    # 110.6 AC4: D13

    def test_his_two_rounds_mean_two_and_a_raise_needs_no_restart(self) -> None:
        self.go()
        self.reader(fields(rounds=2))
        budget = self.open()
        self.assertIn("ROUNDS: 2 extra per boundary", self.opened)
        self.assertEqual(self.ledger("round", "--budget", budget, "--boundary", "7.1", "--use-id", "r1")[0], 0)
        code, out = self.ledger("round", "--budget", budget, "--boundary", "7.1", "--use-id", "r2")
        self.assertEqual(code, 1)  # the last round needs its step-back, as with any number
        self.assertIn("needs a step-back", out)
        self.reader(fields(rounds=3))
        code, out = self.ledger("round", "--budget", budget, "--boundary", "7.1", "--use-id", "r2")
        self.assertEqual(code, 0, out)
        self.assertIn("2 of 3", out)
        self.assertEqual(self.data(budget)["rounds"]["r2"]["value"], 3)

    def test_a_lowered_value_allows_no_more_and_rewrites_nothing(self) -> None:
        self.go()
        self.reader(fields(rounds=4))
        budget = self.open()
        for n in range(1, 3):
            self.assertEqual(self.ledger("round", "--budget", budget, "--boundary", "7.1", "--use-id", f"r{n}")[0], 0)
        self.assertEqual(self.use(budget, "u1")[0], 0)
        self.assertEqual(self.use(budget, "u2")[0], 0)
        self.reader(fields(rounds=1, rechecks={"limit": 1, "ceiling": 4, "per": "boundary", "unit": "count"}))
        code, out = self.ledger("round", "--budget", budget, "--boundary", "7.1", "--use-id", "r3")
        self.assertEqual(code, 1)
        self.assertIn("1 extra per boundary and 2 are used", out)
        self.assertEqual(self.use(budget, "u3")[0], 1)
        data = self.data(budget)
        self.assertEqual([data["rounds"][f"r{n}"]["answer"] for n in (1, 2)], ["TAKEN", "TAKEN"])
        self.assertEqual([data["uses"][f"u{n}"]["answer"] for n in (1, 2)], ["TAKEN", "TAKEN"])

    def test_round_exhaustion_uses_delegated_headroom_without_a_card(self) -> None:
        self.go()
        values = fields(rounds=3)
        values["limits"]["repair_rounds"] = {"limit": 3, "ceiling": 4, "per": "boundary", "unit": "count"}
        self.reader(values)
        budget = self.open()
        take = lambda name: self.ledger("round", "--budget", budget, "--boundary", "7.1", "--use-id", name)
        for name in ("r1", "r2"):
            self.assertEqual(take(name)[0], 0)
        values["rounds"] = values["limits"]["repair_rounds"]["limit"] = 2
        self.reader(values)
        code, out = take("r3")
        self.assertEqual(code, 1)
        self.assertIn("RAISE:", out)
        self.assertIn("limits.repair_rounds.limit=3", out)
        self.assertIn("--expect tok1", out)
        self.assertNotIn("OWNER_CHANGE", out)
        values["rounds"] = values["limits"]["repair_rounds"]["limit"] = 4
        self.reader(values)
        self.assertEqual(take("r3")[0], 1)  # a refused id stays refused after a raise
        self.assertEqual(take("r4")[0], 0)
        self.assertEqual(sum(item["answer"] == "TAKEN" for item in self.data(budget)["rounds"].values()), 3)

    def test_round_exhaustion_names_a_binding_owner_restriction(self) -> None:
        self.go()
        values = fields(rounds=4)
        values["limits"]["repair_rounds"] = {"limit": 4, "ceiling": 8, "per": "boundary", "unit": "count"}
        self.reader(values)
        budget = self.open()
        take = lambda name: self.ledger("round", "--budget", budget, "--boundary", "7.1", "--use-id", name)
        for name in ("r1", "r2"):
            self.assertEqual(take(name)[0], 0)
        code, out = self.ledger("limit", "--budget", budget, "--rounds", "2", "--source", "'two rounds only' 2026-11-08T01:00")
        self.assertEqual(code, 0, out)
        code, out = take("r3")
        self.assertEqual(code, 1)
        self.assertIn("OWNER_LIMIT:", out)
        self.assertNotIn("RAISE:", out)
        self.assertNotIn("OWNER_CHANGE", out)
        values["rounds"] = values["limits"]["repair_rounds"]["limit"] = 8
        self.reader(values)
        self.assertEqual(take("r4")[0], 1)  # YAML cannot remove the later owner restriction
        self.assertEqual(sum(item["answer"] == "TAKEN" for item in self.data(budget)["rounds"].values()), 2)

    def test_round_exhaustion_at_its_yaml_ceiling_requests_an_amendment(self) -> None:
        self.go()
        values = fields(rounds=3)
        values["limits"]["repair_rounds"] = {"limit": 3, "ceiling": 4, "per": "boundary", "unit": "count"}
        self.reader(values)
        budget = self.open()
        take = lambda name: self.ledger("round", "--budget", budget, "--boundary", "7.1", "--use-id", name)
        for name in ("r1", "r2"):
            self.assertEqual(take(name)[0], 0)
        values["rounds"] = values["limits"]["repair_rounds"]["limit"] = 2
        values["limits"]["repair_rounds"]["ceiling"] = 2
        self.reader(values)
        code, out = take("r3")
        self.assertEqual(code, 1)
        self.assertIn("OWNER_CHANGE:", out)
        self.assertNotIn("RAISE:", out)
        self.assertEqual(self.data(budget)["rounds"]["r3"]["answer"], "REFUSED")

    def test_money_is_the_files_value_now_and_never_refills(self) -> None:
        self.go()
        self.reader(fields(money=2))
        budget = self.open()
        job = self.root / "job.sh"
        job.write_text("#!/bin/bash\n")
        launch = lambda name, most: self.ledger("launch", "--budget", budget, "--job", name, "--max", most, "--direct", "--", str(job))  # noqa: E731
        self.assertEqual(launch("a", "2")[0], 0)
        self.assertEqual(self.data(budget)["jobs"]["a"]["cap_used"], 2)
        self.assertEqual(launch("b", "1")[0], 1)
        self.reader(fields(money=3))
        self.assertEqual(launch("c", "1")[0], 0)
        self.reader(fields(money=1))
        self.assertEqual(launch("d", "1")[0], 1)
        self.assertEqual(self.ledger("settle", "--budget", budget, "--job", "a", "--spent", "2")[0], 0)
        self.assertEqual(self.data(budget)["jobs"]["a"]["spent"], 2)
        self.reader(fields(money=None))
        self.assertEqual(launch("e", "1")[0], 1)

    def test_a_deleted_file_keeps_the_last_recorded_version(self) -> None:
        self.go()
        self.reader(fields())
        budget = self.open()
        (self.plan.root / "allowances" / "007.yaml").unlink()
        self.reader(fields(rechecks={"limit": 3, "ceiling": 4, "per": "boundary", "unit": "count"}), hand_edit="the file is deleted on disk; the last recorded version stands")
        self.assertEqual(self.plan.read()["parsed"]["limits"]["rechecks"]["limit"], 3)
        self.assertEqual(self.use(budget, "a")[0], 0)

    def test_a_new_go_without_a_file_returns_to_run_needs_and_keeps_every_use_counted(self) -> None:
        self.go()
        self.reader(fields(rounds=2))
        budget = self.open()
        self.assertEqual(self.ledger("round", "--budget", budget, "--boundary", "7.1", "--use-id", "r1")[0], 0)
        self.assertEqual(self.use(budget, "u1")[0], 0)
        self.body = test_run_needs.epic()
        self.go(None, "2026-10-24")
        self.assertEqual(self.open(), budget)
        data = self.data(budget)
        self.assertEqual(data["rounds"]["r1"]["answer"], "TAKEN")
        self.assertEqual(data["uses"]["u1"]["answer"], "TAKEN")
        self.assertNotIn("allowances", data["gos"][-1])
        # The floor is back, with what was used still used.
        self.assertIn("ROUNDS: 4 extra per boundary", self.opened)
        self.assertIn("7.1 1 used", self.opened)

    def test_a_reapproval_with_the_file_refills_nothing(self) -> None:
        self.go()
        self.reader(fields())
        budget = self.open()
        self.assertEqual(self.use(budget, "a")[0], 0)
        self.assertEqual(self.use(budget, "b")[0], 0)
        self.go(FILE + "# new terms\n", "2026-10-24")
        self.reader(fields())
        self.assertEqual(self.open(), budget)
        self.assertEqual(self.use(budget, "c")[0], 1)

    def test_a_moved_plans_alias_keeps_its_ledger(self) -> None:
        self.go()
        self.reader(fields())
        budget = self.open()
        self.assertEqual(self.use(budget, "a")[0], 0)
        other = f"{'0' * 16}-epic-7"
        folder = self.root / "state" / "dev-auto" / "budgets"
        (folder / f"{other}.alias.json").write_text(json.dumps({"version": 1, "canonical": budget}))
        self.assertEqual(self.use(other, "a")[0], 0)
        self.assertEqual(self.use(other, "b")[0], 0)
        self.assertEqual(self.use(budget, "c")[0], 1)


if __name__ == "__main__":
    unittest.main()
