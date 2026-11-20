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


class StrictEntry:
    """A DirEntry that fails the test on any call that would follow a link."""
    def __init__(self, entry):
        self.entry, self.name = entry, entry.name
    def stat(self, *, follow_symlinks=True):
        if follow_symlinks:
            raise AssertionError('followed a link: ' + self.name)
        return self.entry.stat(follow_symlinks=False)
    def is_dir(self, *, follow_symlinks=True):
        if follow_symlinks:
            raise AssertionError('followed a link: ' + self.name)
        return self.entry.is_dir(follow_symlinks=False)
    def is_file(self, *, follow_symlinks=True):
        if follow_symlinks:
            raise AssertionError('followed a link: ' + self.name)
        return self.entry.is_file(follow_symlinks=False)
    def is_symlink(self):
        return self.entry.is_symlink()


class StrictScandir:
    def __init__(self, real, *args):
        self.it = real(*args)
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        self.it.close()
    def __iter__(self):
        return (StrictEntry(e) for e in self.it)
    def close(self):
        self.it.close()


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

    def add_links(self):
        """A file and a directory outside the tree, both unreadable, plus a dangling link."""
        outside = self.root / 'outside'
        (outside / 'dir').mkdir(parents=True)
        (outside / 'secret.txt').write_text('outside file')
        (outside / 'dir/inner.txt').write_text('outside dir')
        bench = self.tree / '.dev-auto/evidence/qa-bench/x/recovery-root/bin'
        bench.mkdir(parents=True)
        links = {'evidence/qa-bench/x/recovery-root/bin/node': str(outside / 'secret.txt'),
                 'evidence/qa-bench/x/dir-link': str(outside / 'dir'),
                 'evidence/qa-bench/x/dangling': str(outside / 'missing')}
        for name, target in links.items():
            (self.tree / '.dev-auto' / name).symlink_to(target)
        # Any read or traversal of a target now fails, so passing proves no target is read.
        (outside / 'secret.txt').chmod(0)
        (outside / 'dir').chmod(0)
        self.addCleanup((outside / 'dir').chmod, 0o700)
        self.addCleanup((outside / 'secret.txt').chmod, 0o600)
        return outside, links

    def archived_links(self, archive):
        listing = subprocess.run(['tar', '--zstd', '-tvf', str(archive)], check=True, capture_output=True, text=True).stdout
        return {line.split(' -> ')[0].split()[-1][len('.dev-auto/'):]: line.split(' -> ')[1]
                for line in listing.splitlines() if line.startswith('l')}

    def test_symlinks_are_archived_as_links_and_tree_removed(self):
        outside, links = self.add_links()
        expected = cleanup.manifest(self.tree / '.dev-auto')
        for name, target in links.items():
            self.assertEqual(expected[name], {'link': target})
        result = self.run_cleanup()
        self.assertEqual(result['action'], 'removed', result)
        self.assertFalse(self.tree.exists())
        self.assertEqual(result['files'], 5)
        self.assertEqual(cleanup.verify_archive(Path(result['archive']), expected), 5)
        self.assertEqual(self.archived_links(result['archive']), links)
        (outside / 'secret.txt').chmod(0o600)
        (outside / 'dir').chmod(0o700)
        self.assertEqual((outside / 'secret.txt').read_text(), 'outside file')
        self.assertEqual((outside / 'dir/inner.txt').read_text(), 'outside dir')
        self.assertFalse((outside / 'missing').exists())

    def test_manifest_never_follows_a_link_even_to_classify_it(self):
        _, links = self.add_links()
        real = cleanup.os.scandir
        with patch.object(cleanup.os, 'scandir', lambda *a: StrictScandir(real, *a)):
            found = cleanup.manifest(self.tree / '.dev-auto')
        for name, target in links.items():
            self.assertEqual(found[name], {'link': target})

    def test_scan_error_keeps_tree_and_never_counts_as_fresh_manifest(self):
        locked = self.tree / '.dev-auto/evidence/locked'
        locked.mkdir(parents=True)
        (locked / 'late.txt').write_text('added later')
        self.addCleanup(locked.chmod, 0o700)
        locked.chmod(0)
        with self.assertRaises(PermissionError):
            cleanup.manifest(self.tree / '.dev-auto')
        self.assertEqual(self.run_cleanup()['action'], 'kept')
        locked.chmod(0o700)
        original = cleanup.archive_records
        def lock_after_archive(tree, archive):
            count = original(tree, archive)
            (locked / 'later.txt').write_text('added after archiving')
            locked.chmod(0)
            return count
        with patch.object(cleanup, 'archive_records', side_effect=lock_after_archive):
            self.assertEqual(self.run_cleanup()['action'], 'kept')
        self.assertTrue(self.tree.exists())

    def test_linked_handoff_or_records_root_grants_nothing(self):
        handoff = self.tree / '.dev-auto/handoff.md'
        elsewhere = self.root / 'other-handoff.md'
        elsewhere.write_text(handoff.read_text())
        handoff.unlink()
        handoff.symlink_to(elsewhere)
        result = self.run_cleanup()
        self.assertEqual(result['action'], 'kept')
        self.assertIn('handoff', result['reason'])
        self.assertTrue(self.tree.exists())
        with self.assertRaises(SystemExit):
            with patch.dict(sys.modules, run_needs=self.go_stub()):
                cleanup.main(['7', '--project', str(self.tree), '--worktree', str(self.tree)])
        self.assertTrue(self.tree.exists())

    def go_stub(self):
        stub = type(sys)('run_needs')
        stub.run_needs = lambda project, epic: {'state': 'GO', 'parsed': {'may': [cleanup.PERMISSION]}}
        return stub

    def run_main_with_companion(self, dirty, bad_owner_archive=False):
        companion = self.root / 'companion'
        self.git('worktree', 'add', '-b', 'companion', str(companion))
        (companion / '.dev-auto').mkdir()
        (companion / '.dev-auto/handoff.md').write_text('- Run id: run-7\n- Explicit user stop: none\n- Status: COMPLETE\n')
        if dirty:
            (companion / 'changes').write_text('keep me')
        if bad_owner_archive:
            name = self.tree.name + '-' + cleanup.hashlib.sha256(str(self.tree.resolve()).encode()).hexdigest()[:8] + '.tar.zst'
            (self.archive / 'run-7').mkdir(parents=True)
            (self.archive / 'run-7' / name).write_bytes(b'not an archive')
        (self.tree / '.dev-auto/handoff.md').write_text(
            '- Run id: run-7\n- Run checkouts: ' + json.dumps([str(self.tree), str(companion)])
            + '\n- Explicit user stop: none\n- Status: COMPLETE\n')
        with patch.dict(sys.modules, run_needs=self.go_stub()):
            code = cleanup.main(['7', '--project', str(self.tree), '--worktree', str(self.tree), '--worktree', str(companion)])
        return code, companion

    def test_companion_refusal_removes_nothing(self):
        code, companion = self.run_main_with_companion(dirty=True)
        self.assertEqual(code, 1)
        self.assertTrue(self.tree.exists())
        self.assertTrue(companion.exists())
        self.assertEqual(list(self.archive.glob('run-7/*.tar.zst')), [])

    def test_invalid_owner_archive_removes_nothing(self):
        code, companion = self.run_main_with_companion(dirty=False, bad_owner_archive=True)
        self.assertEqual(code, 1)
        self.assertTrue(self.tree.exists())
        self.assertTrue(companion.exists())

    def test_companion_removed_before_owner(self):
        code, companion = self.run_main_with_companion(dirty=False)
        self.assertEqual(code, 0)
        self.assertFalse(self.tree.exists())
        self.assertFalse(companion.exists())
        rows = [json.loads(l) for l in (self.archive / 'run-7/cleanup.jsonl').read_text().splitlines()]
        self.assertEqual([Path(r['path']).name for r in rows], ['companion', 'run'])

    def test_archive_with_changed_link_target_fails_verification(self):
        _, links = self.add_links()
        expected = cleanup.manifest(self.tree / '.dev-auto')
        name = 'evidence/qa-bench/x/dangling'
        archive = self.root / 'a.tar.zst'
        subprocess.run(['tar', '--zstd', '-cf', str(archive), '-C', str(self.tree), '.dev-auto'], check=True)
        changed = dict(expected, **{name: {'link': '/elsewhere'}})
        with self.assertRaises(ValueError):
            cleanup.verify_archive(archive, changed)
        self.assertEqual(cleanup.verify_archive(archive, expected), 5)

    def test_guards_still_keep_tree_with_links(self):
        _, links = self.add_links()
        def kept(reason=None, **options):
            result = self.run_cleanup(**options)
            self.assertEqual(result['action'], 'kept', result)
            if reason:
                self.assertIn(reason, result['reason'])
            self.assertTrue(self.tree.exists())
            for name, target in links.items():
                self.assertEqual(str((self.tree / '.dev-auto' / name).readlink()), target)
        with patch.object(cleanup, 'verify_archive', side_effect=ValueError('archive mismatch')):
            kept('archive mismatch')
        handoff = self.tree / '.dev-auto/handoff.md'
        handoff.write_text('- Run id: run-7\n- Explicit user stop: none\n- Status: ACTIVE\n')
        kept('unfinished')
        handoff.write_text('- Run id: run-7\n- Explicit user stop: none\n- Status: COMPLETE\n')
        (self.tree / 'changes').write_text('keep me')
        kept('uncommitted')
        cleanup.git(self.tree, 'add', 'changes')
        cleanup.git(self.tree, 'commit', '-qm', 'unmerged')
        kept()

    def test_failed_archive_verification_or_symlinked_records_root_keeps_tree(self):
        with patch.object(cleanup, 'verify_archive', side_effect=ValueError('archive mismatch')):
            self.assertIn('archive mismatch', self.run_cleanup()['reason'])
        self.assertTrue(self.tree.exists())
        real = self.root / 'records'
        (self.tree / '.dev-auto').rename(real)
        (self.tree / '.dev-auto').symlink_to(real)
        with self.assertRaisesRegex(ValueError, 'symlinked'):
            cleanup.manifest(self.tree / '.dev-auto')
        self.assertEqual(self.run_cleanup()['action'], 'kept')
        self.assertTrue(self.tree.exists())

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
