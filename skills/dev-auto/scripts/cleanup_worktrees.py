#!/usr/bin/env python3
# MODULE: cleanup_worktrees.py - archive and verify this run's completed, delivered worktrees before removal
"""cleanup_worktrees.py EPIC --project OWNING_CHECKOUT --worktree PATH [--worktree PATH ...]

Permission comes only from the epic's current recorded go. No --force or branch deletion.
The caller must run outside each tree being removed. Kept trees are reported with reasons.
Symlinks in the records are archived as links (path and target text) and never followed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
from handoff_state import finished
from scorecard import field
from run_resources import default_branch, worktree_list

PERMISSION = "remove this run's own worktrees after delivery, once merged, clean and archived"


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


NOFOLLOW_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def records_fd(root):
    """Open the records directory itself, refusing a link."""
    try:
        return os.open(root, NOFOLLOW_DIR)
    except OSError as exc:
        raise ValueError('records directory missing or symlinked') from exc


def read_handoff(tree):
    """Read .dev-auto/handoff.md without following a link at either step."""
    fd = records_fd(tree / '.dev-auto')
    try:
        with os.fdopen(os.open('handoff.md', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd), encoding='utf-8') as stream:
            return stream.read()
    except OSError as exc:
        raise ValueError('handoff missing, unreadable or symlinked') from exc
    finally:
        os.close(fd)


def manifest(root):
    """Map each record to its SHA-256, or a symlink to {'link': target text}.

    No link is followed, even to classify it; any scan error propagates.
    """
    result = {}

    def scan(fd, prefix):
        with os.scandir(fd) as entries:
            items = sorted(entries, key=lambda e: e.name)
        for entry in items:
            key = prefix + entry.name
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode):
                result[key] = {'link': os.readlink(entry.name, dir_fd=fd)}
            elif stat.S_ISREG(mode):
                digest = hashlib.sha256()
                with os.fdopen(os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd), 'rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block)
                result[key] = digest.hexdigest()
            elif stat.S_ISDIR(mode):
                child = os.open(entry.name, NOFOLLOW_DIR, dir_fd=fd)
                try:
                    scan(child, key + '/')
                finally:
                    os.close(child)
            else:
                raise ValueError('records contain a special file')

    fd = records_fd(root)
    try:
        scan(fd, '')
    finally:
        os.close(fd)
    return result


def verify_archive(archive, expected):
    found = {}
    with subprocess.Popen(['zstd', '-dc', '--', str(archive)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        try:
            with tarfile.open(fileobj=proc.stdout, mode='r|') as tar:
                for member in tar:
                    if member.isdir():
                        continue
                    if not (member.isfile() or member.issym()) or not member.name.startswith('.dev-auto/'):
                        raise ValueError('unexpected archive member')
                    name = member.name[len('.dev-auto/'):]
                    if name in found or '..' in Path(name).parts:
                        raise ValueError('duplicate or unsafe archive member')
                    if member.issym():
                        found[name] = {'link': member.linkname}
                        continue
                    digest = hashlib.sha256()
                    with tar.extractfile(member) as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            digest.update(block)
                    found[name] = digest.hexdigest()
            if proc.wait() != 0:
                raise ValueError('zstd verification failed')
        finally:
            proc.stdout.close()
            proc.stderr.close()
    if found != expected:
        raise ValueError('archive file count or hashes differ')
    return len(found)


def archive_records(tree, destination):
    expected = manifest(tree / '.dev-auto')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        fd, temp = tempfile.mkstemp(prefix='.archive-', suffix='.tar.zst', dir=destination.parent)
        os.close(fd)
        try:
            subprocess.run(['tar', '--zstd', '-cf', temp, '-C', str(tree), '.dev-auto'], check=True, capture_output=True)
            verify_archive(Path(temp), expected)
            os.replace(temp, destination)
        finally:
            Path(temp).unlink(missing_ok=True)
    count = verify_archive(destination, expected)
    if manifest(tree / '.dev-auto') != expected:
        raise ValueError('source records changed while archiving')
    return count


def cleanup(tree, *, run_id, checkouts, permission, archive_root, prepare_only=False):
    tree = tree.resolve()
    result = {'path': str(tree), 'action': 'kept'}
    try:
        if not permission:
            raise ValueError('go has no cleanup permission; owner card required')
        if str(tree) not in checkouts:
            raise ValueError('not this run\'s checkout')
        rows = worktree_list(tree)
        current = next((r for r in rows if Path(r['worktree']).resolve() == tree), None)
        main = Path(rows[0]['worktree']).resolve()
        if current is None or tree == main or 'locked' in current:
            raise ValueError('not an unlocked linked worktree')
        body = read_handoff(tree)
        if field(body, 'Run id') != run_id or not finished(body):
            raise ValueError('different run, unfinished, or explicit stop')
        branch = default_branch(main)
        if branch is None or git(main, 'symbolic-ref', '--short', 'HEAD') != branch:
            raise ValueError('default checkout is not on its resolved default branch')
        head = git(tree, 'rev-parse', 'HEAD')
        git(main, 'merge-base', '--is-ancestor', head, branch)
        git(main, 'merge-base', '--is-ancestor', head, f'origin/{branch}')
        if git(tree, 'status', '--porcelain=v1', '--untracked-files=all'):
            raise ValueError('uncommitted files')
        # inventory must already have been checked by the lead; archive and remove no process.
        size = int(subprocess.run(['du', '-s', '--block-size=1', '--', str(tree)], check=True, capture_output=True, text=True).stdout.split()[0])
        name = tree.name + '-' + hashlib.sha256(str(tree).encode()).hexdigest()[:8] + '.tar.zst'
        archive = archive_root / run_id / name
        if archive.is_relative_to(tree):
            raise ValueError('archive destination lies inside removed worktree')
        count = archive_records(tree, archive)
        if prepare_only:
            result.update(action='archived', archive=str(archive), files=count)
            return result
        # Recheck identities and clean state immediately before removal. Git itself refuses changes.
        if git(tree, 'rev-parse', 'HEAD') != head or git(tree, 'status', '--porcelain=v1', '--untracked-files=all'):
            raise ValueError('checkout changed after archiving')
        if read_handoff(tree) != body:
            raise ValueError('handoff changed after archiving')
        verify_archive(archive, manifest(tree / '.dev-auto'))
        git(main, 'worktree', 'remove', str(tree))
        result.update(action='removed', bytes=size, archive=str(archive), files=count,
                      archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
        result['reason'] = str(exc) if not isinstance(exc, subprocess.SubprocessError) else 'Git/archive command refused or ancestry unproved'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('epic', type=int)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--worktree', type=Path, action='append', required=True)
    args = parser.parse_args(argv)
    import run_needs
    needs = run_needs.run_needs(args.project, args.epic)
    try:
        body = read_handoff(args.project)
    except ValueError as exc:
        parser.error(str(exc))
    run_id = field(body, 'Run id')
    if not run_id or not re.fullmatch(r'[\w-]+', run_id):
        parser.error('handoff needs a safe Run id')
    checkouts = json.loads(field(body, 'Run checkouts') or '[]')
    permission = needs['state'] == 'GO' and PERMISSION in needs['parsed'].get('may', []) and finished(body)
    # Every repository archives into the owning project's default checkout.
    archive_root = Path(worktree_list(args.project)[0]['worktree']) / '.dev-auto/archive'
    # The owning checkout goes last so its handoff stays for a retry. Every tree is checked,
    # archived and verified before any is removed, and the first refusal stops the rest.
    project = args.project.resolve()
    trees = sorted(args.worktree, key=lambda t: t.resolve() == project)
    log = archive_root / run_id / 'cleanup.jsonl'
    options = dict(run_id=run_id, checkouts=checkouts, permission=permission, archive_root=archive_root)
    for prepare_only in (True, False):
        for tree in trees:
            result = cleanup(tree, prepare_only=prepare_only, **options)
            if prepare_only and result['action'] == 'archived':
                continue
            print(json.dumps(result))
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open('a') as out:
                out.write(json.dumps(result) + '\n')
            if result['action'] != 'removed':
                return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
