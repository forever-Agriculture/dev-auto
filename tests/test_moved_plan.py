# MODULE: test_moved_plan.py - Epic 107 old BMAD approvals survive a move without minting a Go
import json
import contextlib
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/dev-auto/scripts"))
import run_needs
import spend_ledger

TEXT = "# Epic 7: Fixture\n\n## Run needs\n- **Extra repair rounds:** 3 per boundary.\n- **Money cap:** $12.\n\n## Decisions\nKeep every round.\n\n### Story 7.1: Keep the original requirement.\n"
OLD = "_bmad-output/implementation-artifacts/sprint-status.yaml"


class MovedPlanTests(unittest.TestCase):
    def test_identity_deadline_covers_every_history_call_and_never_falls_back_after_expiry(self):
        self.move()
        real_run = subprocess.run
        for budget in (1.5, 0.25):
            with self.subTest(budget=budget):
                clock, observed = [100.0], []
                def run(argv, **options):
                    self.assertLess(clock[0], 100 + budget, "no subprocess may start after the identity deadline")
                    observed.append(options["timeout"])
                    self.assertLessEqual(options["timeout"], 100 + budget - clock[0] + 0.00001)
                    clock[0] += 0.1
                    return real_run(argv, **options)
                with mock.patch("time.monotonic", side_effect=lambda: clock[0]), mock.patch.object(subprocess, "run", side_effect=run):
                    if budget == 1.5:
                        self.assertIn("::_bmad-output", spend_ledger.plan_identity(str(self.repo / "plan"), timeout=budget))
                    else:
                        with self.assertRaises(subprocess.TimeoutExpired):
                            spend_ledger.plan_identity(str(self.repo / "plan"), timeout=budget)
                self.assertGreater(len(observed), 1)
                self.assertEqual(observed, sorted(observed, reverse=True))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git("init", "-qb", "main")
        self.file(OLD, "development_status:\n  epic-7: backlog\n")
        self.file("_bmad-output/planning-artifacts/epics.md", TEXT)
        self.commit("old plan")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", *args], text=True, env={**os.environ, "GIT_AUTHOR_DATE": "2026-11-01T12:00:00Z", "GIT_COMMITTER_DATE": "2026-11-01T12:00:00Z"}).strip()

    def file(self, name, text):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def read(self, moved=False):
        status = {"ok": True, "format": "bmn-plan" if moved else "bmad", "history": "product-repository", "product_root": str(self.repo), "board_checkout": str(self.repo), "default_checkout": str(self.repo), "plan_root": str(self.repo / ("plan" if moved else "_bmad-output")), "board": str(self.repo / ("plan/status.yaml" if moved else OLD))}
        with mock.patch.object(run_needs, "resolve", return_value=status):
            return run_needs.run_needs(self.repo, 7)

    def move(self, status="in-progress", note="go 2026-11-01"):
        anchor = self.git("rev-parse", "HEAD")
        self.file("plan/status.yaml", f"format: bmn-plan\nschema_version: 1\nmoved_from: {OLD}\nqueue: []\ndevelopment_status:\n  epic-7: {status} # {note}\n  7-1-keep: backlog\n")
        self.file("plan/migration.json", json.dumps({"version": 1, "source_board": OLD, "history_head": anchor}))
        self.file("plan/epics/007-fixture.md", "<!-- bmn-plan: bmad-legacy -->\n" + TEXT)
        (self.repo / OLD).unlink()
        self.commit("plan: migrate without a new Go")

    def test_existing_go_keeps_its_commit_text_hash_and_terms_when_old_board_is_removed(self):
        self.file(OLD, "development_status:\n  epic-7: in-progress # go 2026-11-01\n")
        original = self.commit("old BMAD Go")
        before = self.read()
        self.assertEqual(before["state"], "GO")
        self.move()
        after = self.read(True)
        for key in ("state", "go_commit", "go_date", "approved_text", "parsed", "stories"):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(after["go_commit"], original)

    def test_working_migration_metadata_cannot_replace_the_original_withdrawal_history_or_identity(self):
        alternate = "older/implementation-artifacts/sprint-status.yaml"
        self.file(OLD, "development_status:\n  epic-7: in-progress # go 2026-11-01\n")
        self.file(alternate, "development_status:\n  epic-7: in-progress # go 2026-11-01\n")
        original_go = self.commit("old Go on two retained boards")
        self.file(OLD, "development_status:\n  epic-7: backlog # withdrawal on the original board\n")
        self.commit("withdraw original")
        self.move()
        self.assertIn("withdrawn_go", self.read(True))
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.repo / "state")}):
            identity = spend_ledger.plan_identity(str(self.repo / "plan"))
            budget = hashlib.sha256(identity.encode()).hexdigest()[:16] + "-epic-7"
            with (ledger := spend_ledger.Ledger(budget)) as data:
                data["rounds"]["spent"] = {"answer": "TAKEN", "boundary": "7.1"}
                data.update(plan_root=str(self.repo / "_bmad-output"), project=str(self.repo), epic=7)
                data["gos"].append({"kind": "go", "commit": original_go, "cap": 12, "rounds": 3, "stories": ["7.1"]})
                ledger.save()
            before = {p.name: p.read_bytes() for p in spend_ledger.budgets().iterdir()}
            original_board = (self.repo / "plan/status.yaml").read_text()
            original_metadata = (self.repo / "plan/migration.json").read_text()
            for mutation in ("substitute", "remove-header", "remove-metadata"):
                with self.subTest(mutation=mutation):
                    self.file("plan/status.yaml", original_board)
                    self.file("plan/migration.json", original_metadata)
                    if mutation == "substitute":
                        self.file("plan/status.yaml", original_board.replace(OLD, alternate))
                        self.file("plan/migration.json", json.dumps({"version": 1, "source_board": alternate, "history_head": self.git("rev-parse", "HEAD")}))
                    elif mutation == "remove-header":
                        self.file("plan/status.yaml", original_board.replace(f"moved_from: {OLD}\n", ""))
                    else:
                        (self.repo / "plan/migration.json").unlink()
                    result = self.read(True)
                    self.assertTrue(result.get("unconfirmed"), result)
                    self.assertNotEqual(result["state"], "GO")
                    with self.assertRaises((ValueError, RuntimeError, OSError)):
                        spend_ledger.plan_identity(str(self.repo / "plan"))
                    with mock.patch.object(run_needs, "run_needs", return_value=result), contextlib.redirect_stdout(io.StringIO()):
                        self.assertNotEqual(spend_ledger.main(["open", "--epic", "7", "--project", str(self.repo)]), 0)
                        self.assertNotEqual(spend_ledger.main(["round", "--budget", budget, "--boundary", "epic", "--use-id", mutation]), 0)
                    self.assertEqual({p.name: p.read_bytes() for p in spend_ledger.budgets().iterdir()}, before)

    def test_withdrawn_go_stays_withdrawn_after_a_later_in_progress_snapshot(self):
        self.file(OLD, "development_status:\n  epic-7: in-progress # go 2026-11-01\n")
        self.commit("old Go")
        self.file(OLD, "development_status:\n  epic-7: backlog # put back\n")
        self.commit("withdraw")
        before = self.read()
        self.move()
        after = self.read(True)
        self.assertEqual(after["state"], before["state"])
        self.assertEqual(after["withdrawn_go"], before["withdrawn_go"])
        self.assertEqual(after["go_commit"], before["go_commit"])

    def test_copied_uncommitted_date_and_legacy_new_go_grant_nothing(self):
        self.move(status="ready")
        result = self.read(True)
        self.assertEqual(result["state"], "NEEDS_NORMALIZE")
        self.assertFalse(result.get("floor"))
        self.assertNotIn("go_commit", result)

    def test_a_real_new_record_after_normalization_is_read_in_the_new_plan(self):
        self.file(OLD, "development_status:\n  epic-7: in-progress # go 2026-11-01\n")
        self.commit("old Go")
        self.move()
        normalized = TEXT.replace("Keep every round.", "New approved terms.")
        self.file("plan/epics/007-fixture.md", normalized)
        self.file("plan/status.yaml", (self.repo / "plan/status.yaml").read_text().replace("in-progress", "ready").replace("2026-11-01", "2026-11-02"))
        approved = run_needs.approval_text(run_needs.sections(normalized))
        commit = self.commit(f'plan: new Go\n\nGo-Epic: 7\nGo-Date: 2026-11-02\nApproval-Source: "Go" 2026-11-02T12:00\nApproved-Text: sha256:{approved}\nApproved-File: plan/epics/007-fixture.md')
        result = self.read(True)
        self.assertEqual((result["state"], result["go_commit"]), ("GO", commit))
        self.assertEqual(result["approved_text"], "sha256:" + approved)

    def test_ledger_keeps_original_file_lock_consumption_and_alias_after_move(self):
        self.file(OLD, "development_status:\n  epic-7: ready-for-dev # go 2026-11-01\n")
        self.commit("old Go")
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.repo / "state")}):
            def open_budget(moved):
                out = io.StringIO()
                with mock.patch.object(run_needs, "run_needs", return_value=self.read(moved)), contextlib.redirect_stdout(out):
                    self.assertEqual(spend_ledger.main(["open", "--epic", "7", "--project", str(self.repo)]), 0, out.getvalue())
                return out.getvalue().split()[1].rstrip(":")
            budget = open_budget(False)
            with (ledger := spend_ledger.Ledger(budget)) as data:
                data["rounds"]["already-spent"] = {"answer": "TAKEN", "boundary": "7.1"}
                data["jobs"]["outstanding"] = {"answer": "UNKNOWN", "state": "unknown", "max": 2.5}
                ledger.save()
            original = (spend_ledger.budgets() / f"{budget}.json").read_bytes()
            lock = spend_ledger.budgets() / f"{budget}.lock"
            inode = lock.stat().st_ino
            self.move(status="ready")
            self.assertEqual(open_budget(True), budget)
            self.assertEqual(lock.stat().st_ino, inode)
            after = json.loads((spend_ledger.budgets() / f"{budget}.json").read_text())
            before = json.loads(original)
            for key in ("gos", "rounds", "jobs"):
                self.assertEqual(after[key], before[key], key)
            aliases = list(spend_ledger.budgets().glob("*.alias.json"))
            self.assertEqual(len(aliases), 1)
            current_id = aliases[0].name.removesuffix(".alias.json")
            with spend_ledger.Ledger(current_id) as shared:
                self.assertEqual(shared["rounds"], before["rounds"])
            self.assertFalse((spend_ledger.budgets() / f"{current_id}.json").exists())

    def test_reapproving_after_move_keeps_spent_rounds_and_outstanding_money(self):
        self.file(OLD, "development_status:\n  epic-7: ready-for-dev # go 2026-11-01\n")
        self.commit("old Go")
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.repo / "state")}):
            def opened(moved):
                out = io.StringIO()
                with mock.patch.object(run_needs, "run_needs", return_value=self.read(moved)), contextlib.redirect_stdout(out):
                    self.assertEqual(spend_ledger.main(["open", "--epic", "7", "--project", str(self.repo)]), 0, out.getvalue())
                return out.getvalue().split()[1].rstrip(":")
            budget = opened(False)
            with (ledger := spend_ledger.Ledger(budget)) as data:
                data["rounds"]["spent-1"] = {"answer": "TAKEN", "boundary": "7.1"}
                data["rounds"]["spent-2"] = {"answer": "TAKEN", "boundary": "7.1"}
                data["jobs"]["outstanding"] = {"state": "unknown", "max": 2.5}
                ledger.save()
            path = spend_ledger.budgets() / f"{budget}.json"
            before = json.loads(path.read_text())
            lock_inode = path.with_suffix(".lock").stat().st_ino
            self.move(status="ready")
            self.assertEqual(opened(True), budget)
            normalized = TEXT.replace("Keep every round.", "New approved terms.")
            self.file("plan/epics/007-fixture.md", normalized)
            self.file("plan/status.yaml", (self.repo / "plan/status.yaml").read_text().replace("2026-11-01", "2026-11-02"))
            approved = run_needs.approval_text(run_needs.sections(normalized))
            self.commit(f'plan: new Go\n\nGo-Epic: 7\nGo-Date: 2026-11-02\nApproval-Source: "Go" 2026-11-02T12:00\nApproved-Text: sha256:{approved}\nApproved-File: plan/epics/007-fixture.md')
            self.assertEqual(opened(True), budget)
            after = json.loads(path.read_text())
            self.assertEqual(after["rounds"], before["rounds"])
            self.assertEqual(after["jobs"], before["jobs"])
            self.assertEqual(spend_ledger.rounds_used(after, "7.1"), 2)
            self.assertEqual(spend_ledger.totals(after), spend_ledger.totals(before))
            self.assertEqual(len(after["gos"]), len(before["gos"]) + 1)
            self.assertEqual(path.with_suffix(".lock").stat().st_ino, lock_inode)

    def test_no_go_legacy_open_keeps_an_existing_ledger_byte_for_byte(self):
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.repo / "state")}):
            identity = spend_ledger.plan_identity(str(self.repo / "_bmad-output"))
            budget = hashlib.sha256(identity.encode()).hexdigest()[:16] + "-epic-7"
            with (ledger := spend_ledger.Ledger(budget)) as data:
                data["rounds"]["spent"] = {"answer": "TAKEN", "boundary": "7.1"}
                ledger.save()
            path = spend_ledger.budgets() / f"{budget}.json"
            before = path.read_bytes()
            self.move(status="backlog", note="no Go")
            with mock.patch.object(run_needs, "run_needs", return_value=self.read(True)), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(spend_ledger.main(["open", "--epic", "7", "--project", str(self.repo)]), 0)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(list(spend_ledger.budgets().glob("*-epic-7.json"))), 1)

    def test_active_exhausted_withdrawn_resumed_and_outstanding_snapshots_survive_move(self):
        original_repo = self.repo
        try:
            for mode in ("active", "exhausted", "withdrawn", "resumed", "outstanding"):
                with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                    self.repo = Path(folder)
                    self.git("init", "-qb", "main")
                    self.file(OLD, "development_status:\n  epic-7: ready-for-dev # go 2026-11-01\n")
                    self.file("_bmad-output/planning-artifacts/epics.md", TEXT)
                    self.commit("old approved plan")
                    with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.repo / "state")}):
                        def opened(moved):
                            needs = self.read(moved)
                            out = io.StringIO()
                            with mock.patch.object(run_needs, "run_needs", return_value=needs), contextlib.redirect_stdout(out):
                                self.assertEqual(spend_ledger.main(["open", "--epic", "7", "--project", str(self.repo)]), 0, out.getvalue())
                            return out.getvalue().split()[1].rstrip(":"), needs
                        budget, _ = opened(False)
                        with (ledger := spend_ledger.Ledger(budget)) as data:
                            for i in range(4 if mode == "exhausted" else 1):
                                data["rounds"][f"used-{i}"] = {"answer": "TAKEN", "boundary": "7.1"}
                            if mode == "outstanding":
                                data["jobs"]["hold"] = {"answer": "UNKNOWN", "state": "unknown", "max": 2.5}
                            ledger.save()
                        if mode in ("withdrawn", "resumed"):
                            self.file(OLD, "development_status:\n  epic-7: backlog # put back\n")
                            self.commit("withdraw")
                            opened(False)
                        if mode == "resumed":
                            self.file(OLD, "development_status:\n  epic-7: ready-for-dev # go 2026-11-02\n")
                            self.commit("new old-format Go")
                        elif mode != "withdrawn":
                            self.file(OLD, "development_status:\n  epic-7: in-progress # go 2026-11-01\n")
                            self.commit("run active")
                        _, before_needs = opened(False)
                        path = spend_ledger.budgets() / f"{budget}.json"
                        before = json.loads(path.read_text())
                        status, note = run_needs.row((self.repo / OLD).read_text(), 7)
                        self.move(status={"ready-for-dev": "ready"}.get(status, status), note=note)
                        moved_budget, after_needs = opened(True)
                        self.assertEqual(moved_budget, budget)
                        for key in ("state", "go_commit", "go_date", "approved_text", "parsed", "withdrawn_go"):
                            self.assertEqual(after_needs.get(key), before_needs.get(key), key)
                        after = json.loads(path.read_text())
                        for key in ("gos", "rounds", "jobs"):
                            self.assertEqual(after[key], before[key], key)
                        self.assertEqual(spend_ledger.rounds_used(after, "7.1"), 4 if mode == "exhausted" else 1)
        finally:
            self.repo = original_repo

    def test_alias_refuses_split_data_and_alias_chains_without_changing_either_budget(self):
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.repo / "state")}):
            old, new, third = "1" * 16 + "-epic-7", "2" * 16 + "-epic-7", "3" * 16 + "-epic-7"
            with (ledger := spend_ledger.Ledger(old)):
                ledger.save()
            with (other := spend_ledger.Ledger(new)):
                other.save()
            before = {key: (spend_ledger.budgets() / f"{key}.json").read_bytes() for key in (old, new)}
            with (ledger := spend_ledger.Ledger(old)):
                with self.assertRaisesRegex(ValueError, "MIGRATION_LEDGER_SPLIT"):
                    ledger.alias(new)
            for key, value in before.items():
                self.assertEqual((spend_ledger.budgets() / f"{key}.json").read_bytes(), value)
            self.assertFalse((spend_ledger.budgets() / f"{new}.alias.json").exists())
            with (ledger := spend_ledger.Ledger(old)):
                ledger.alias(third)
            (spend_ledger.budgets() / f"{new}.alias.json").write_text(json.dumps({"version": 1, "canonical": third}))
            with self.assertRaisesRegex(ValueError, "alias chains"):
                spend_ledger.Ledger(new)
