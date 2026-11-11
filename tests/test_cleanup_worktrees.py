# MODULE: test_cleanup_worktrees.py - real scratch Git lifecycle and fail-closed archive/removal guards
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/dev-auto/scripts'))
import cleanup_worktrees as cleanup


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.main = self.root / 'main'
        self.main.mkdir()
        self.git('init', '-qb', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.main / '.gitignore').write_text('.dev-auto/\n')
        self.git('add', '.gitignore')
        self.git('commit', '-qm', 'base')
        self.git('update-ref', 'refs/remotes/origin/main', 'main')
        self.tree = self.root / 'run'
        self.git('worktree', 'add', '-b', 'run', str(self.tree))
        state = self.tree / '.dev-auto'
        state.mkdir()
        (state / 'handoff.md').write_text('- Run id: run-7\n- Explicit user stop: none\n- Status: COMPLETE\n')
        (state / 'evidence.json').write_text('{"synthetic":true}')
        self.archive = self.main / '.dev-auto/archive'

    def git(self, *args):
        return cleanup.git(self.main, *args)

    def run_cleanup(self, **kwargs):
        return cleanup.cleanup(self.tree, run_id=kwargs.get('run_id', 'run-7'),
                               checkouts=[str(self.tree)] if kwargs.get('own', True) else [],
                               permission=kwargs.get('permission', True), archive_root=self.archive)

    def test_archives_counts_and_hashes_before_removing_own_merged_clean_tree(self):
        expected = cleanup.manifest(self.tree / '.dev-auto')
        result = self.run_cleanup()
        self.assertEqual(result['action'], 'removed', result)
        self.assertFalse(self.tree.exists())
        self.assertEqual(result['files'], 2)
        self.assertEqual(cleanup.verify_archive(Path(result['archive']), expected), 2)
        self.assertEqual(result['archive_sha256'], hashlib.sha256(Path(result['archive']).read_bytes()).hexdigest())
        self.assertIn('run', self.git('branch', '--list'))  # no branch deletion

    def test_no_permission_different_run_or_foreign_checkout_are_kept(self):
        for options, reason in (({'permission': False}, 'no cleanup permission'), ({'run_id': 'another'}, 'different run'), ({'own': False}, 'not this run')):
            result = self.run_cleanup(**options)
            self.assertEqual(result['action'], 'kept')
            self.assertIn(reason, result['reason'])
            self.assertTrue(self.tree.exists())
        self.assertFalse(self.archive.exists())

    def test_dirty_or_unmerged_tree_is_kept(self):
        f = self.tree / 'changes'
        f.write_text('keep me')
        self.assertIn('uncommitted', self.run_cleanup()['reason'])
        cleanup.git(self.tree, 'add', 'changes')
        cleanup.git(self.tree, 'commit', '-qm', 'unmerged')
        self.assertEqual(self.run_cleanup()['action'], 'kept')
        self.assertEqual(f.read_text(), 'keep me')

    def test_missing_remote_delivery_is_kept(self):
        self.git('update-ref', '-d', 'refs/remotes/origin/main')
        self.assertEqual(self.run_cleanup()['action'], 'kept')
        self.assertTrue(self.tree.exists())

    def test_failed_archive_verification_or_symlink_keeps_tree(self):
        with patch.object(cleanup, 'verify_archive', side_effect=ValueError('archive mismatch')):
            self.assertIn('archive mismatch', self.run_cleanup()['reason'])
        self.assertTrue(self.tree.exists())
        (self.tree / '.dev-auto/linked').symlink_to(self.main / '.gitignore')
        self.assertIn('symlink', self.run_cleanup()['reason'])

    def test_source_mutation_during_archive_prevents_removal(self):
        original = cleanup.archive_records
        def mutate(tree, archive):
            count = original(tree, archive)
            (tree / '.dev-auto/handoff.md').write_text('changed')
            return count
        with patch.object(cleanup, 'archive_records', side_effect=mutate):
            result = self.run_cleanup()
        self.assertEqual(result['action'], 'kept')
        self.assertTrue(self.tree.exists())

    def test_non_handoff_evidence_mutation_after_archive_keeps_tree(self):
        original = cleanup.archive_records
        def mutate(tree, archive):
            count = original(tree, archive)
            (tree / '.dev-auto/evidence.json').write_text('new evidence')
            return count
        with patch.object(cleanup, 'archive_records', side_effect=mutate):
            self.assertEqual(self.run_cleanup()['action'], 'kept')
        self.assertTrue(self.tree.exists())

    def test_resolved_trunk_default_uses_shared_inventory_policy(self):
        self.git('branch', '-m', 'main', 'trunk')
        self.git('update-ref', 'refs/remotes/origin/trunk', 'trunk')
        self.git('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/trunk')
        self.assertEqual(self.run_cleanup()['action'], 'removed')
        self.assertFalse(self.tree.exists())
