#!/usr/bin/env python3
# MODULE: scorecard.py - read-only per-run counts from ledger, ask metadata and review dispositions
"""scorecard.py EPIC --project P [--json] [--check]

Reads only the handoff, budget JSON, and ask request.json/outcome.json metadata.
Missing evidence is unknown; --check fails for unknowns or uncounted full reviews/rechecks.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
REVIEW = re.compile(r'^\s*(?:- )?review ([\w-]+): (\d+) findings, (\d+) repaired, (\d+) rejected, (\d+) deferred\s*$', re.M)
CONSULT = re.compile(r'\b([\w-]+): (unblocked|partly|not)\b')


def stamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp missing')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timestamp needs timezone')
    return result


def field(body, name):
    match = re.search(r'^- ' + re.escape(name) + r': (.+)$', body, re.M)
    return match[1].strip() if match else None


def read_json(path, unknown):
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError('expected an object')
        return data
    except (OSError, ValueError) as exc:
        unknown.append(f'{path.name} ({path.parent.name}): {type(exc).__name__}')
        return None


def summarize(epic, body, ledger, runs, *, limits=None, now=None):
    unknown = []
    now = now or datetime.now(timezone.utc)
    try:
        checkouts = json.loads(field(body, 'Run checkouts') or '[]')
        if not isinstance(checkouts, list) or not all(isinstance(p, str) for p in checkouts):
            raise ValueError('checkout list')
    except ValueError:
        checkouts = []
    if not checkouts:
        unknown.append('Run checkouts missing from handoff')
    start = field(body, 'Run started')
    end = field(body, 'Run finished')
    try:
        since = stamp(start)
        until = stamp(end) if end else now
        if since > until:
            raise ValueError('run ends before start')
        hours = (until - since).total_seconds() / 3600
    except (ValueError, TypeError):
        since = until = None
        hours = None
        unknown.append('Run started/finished timestamp')
    roles, reviews, consults = {}, [], []
    review_lines = {}
    for match in REVIEW.finditer(body):
        rid, *counts = match.groups()
        values = list(map(int, counts))
        if rid in review_lines or values[0] != sum(values[1:]):
            unknown.append(f'review {rid}: duplicate or inconsistent finding counts')
        review_lines[rid] = dict(zip(('findings', 'repaired', 'rejected', 'deferred'), values))
    if not runs.is_dir():
        unknown.append('ask records directory missing')
    else:
        try:
            directories = sorted(runs.iterdir())
        except OSError:
            directories = []
            unknown.append('ask records directory unreadable')
        for directory in directories:
            if directory.name.startswith('.') or not directory.is_dir():
                continue
            request = read_json(directory / 'request.json', unknown)
            if request is None:
                continue
            if 'project' not in request:
                unknown.append(f'{directory.name}: request metadata unknown')
                continue
            if request.get('project') not in checkouts or since is None:
                continue
            if not all(isinstance(request.get(k), str) and request[k] for k in ('id', 'role', 'asked_at')):
                unknown.append(f'{directory.name}: request metadata unknown')
                continue
            try:
                at = stamp(request['asked_at'])
            except (ValueError, KeyError, TypeError):
                unknown.append(f'{directory.name}: asked_at unknown')
                continue
            if not since <= at <= until:
                continue
            rid = request.get('id', directory.name)
            role = request.get('role') or 'unknown'
            row = roles.setdefault(role, {'asks': 0, 'agents': [], 'minutes': 0.0})
            row['asks'] += 1
            outcome = read_json(directory / 'outcome.json', unknown)
            observed = (outcome or {}).get('observed') or {}
            if not isinstance(observed, dict):
                observed = {}
                unknown.append(f'{rid}: observed route unknown')
            if not all(isinstance(observed.get(k), str) and observed[k] for k in ('model', 'effort')):
                unknown.append(f'{rid}: observed route unknown')
            route = f"{observed.get('model', 'unknown')}/{observed.get('effort', 'unknown')}"
            if route not in row['agents']:
                row['agents'].append(route)
            try:
                duration = (stamp(outcome['ended_at']) - stamp(outcome['started_at'])).total_seconds() / 60
                if duration < 0:
                    raise ValueError('negative duration')
                if row['minutes'] is not None:
                    row['minutes'] += duration
            except (KeyError, TypeError, ValueError):
                row['minutes'] = None
                unknown.append(f'{rid}: duration unknown')
            recheck = request.get('phase') == 'recheck' or bool(request.get('recheck_of'))
            full = role in ('epic-reviewer', 'small-epic-reviewer', 'final-reviewer')
            if full or recheck:
                counts = review_lines.get(rid)
                reviews.append({'id': rid, 'role': role, 'recheck': recheck,
                                'counts': counts, 'status': 'counted' if counts else 'not counted'})
            if role in ('consultant', 'senior-consultant'):
                outcomes = [m[2] for m in CONSULT.finditer(body) if m[1] == rid]
                consults.append({'id': rid, 'outcome': outcomes[0] if len(outcomes) == 1 else None})
    boundaries = {}
    if ledger is None:
        unknown.append('ledger unknown')
    else:
        if ledger.get('epic') != epic:
            unknown.append('ledger epic differs')
        complete = {}
        for collection in ('uses', 'rounds'):
            values = ledger.get(collection)
            complete[collection] = isinstance(values, dict)
            for use in values.values() if isinstance(values, dict) else ():
                if not isinstance(use, dict) or use.get('answer') not in ('TAKEN', 'REFUSED'):
                    complete[collection] = False
                    continue
                if use['answer'] == 'REFUSED':
                    continue
                name = 'repair_rounds' if collection == 'rounds' else use.get('limit')
                boundary = use.get('boundary')
                quantity = 1 if collection == 'rounds' else use.get('amount')
                spec = (limits or {}).get(name, {}) if isinstance(name, str) else {}
                per = 'boundary' if collection == 'rounds' else spec.get('per', use.get('per'))
                if (not isinstance(name, str) or not isinstance(boundary, str) or
                        per not in ('epic', 'boundary') or isinstance(quantity, bool) or
                        not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity <= 0):
                    complete[collection] = False
                    continue
                target = 'epic' if per == 'epic' else boundary
                row = boundaries.setdefault(target, {})
                entry = row.setdefault(name, {'used': 0, 'limit': use.get('value'), 'per': per})
                entry['used'] += quantity
            if not complete[collection]:
                unknown.append(f'ledger {collection} unknown')
        if limits is not None:
            for boundary in set(boundaries) | {'epic'}:
                row = boundaries.setdefault(boundary, {})
                for name, spec in limits.items():
                    if spec['per'] == 'epic' and boundary != 'epic':
                        continue
                    entry = row.setdefault(name, {'used': 0})
                    entry.update(limit=spec['limit'], per=spec['per'])
                    collection = 'rounds' if name == 'repair_rounds' else 'uses'
                    if name != 'money_usd' and not complete[collection]:
                        entry['known_used'], entry['used'] = entry['used'], None
        if limits is not None and 'money_usd' in limits:
            jobs = ledger.get('jobs')
            spent = 0
            if not isinstance(jobs, dict):
                spent = None
            else:
                for job in jobs.values():
                    if not isinstance(job, dict) or job.get('state') not in ('settled', 'reserved', 'started', 'unknown', 'released'):
                        spent = None
                        break
                    value = job.get('spent') if job['state'] == 'settled' else (job.get('max') if job['state'] in ('reserved', 'started', 'unknown') else 0)
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                        spent = None
                        break
                    spent += value
            boundaries['epic']['money_usd']['used'] = spent
            if spent is None:
                unknown.append('ledger money usage unknown')
    if limits is None:
        unknown.append('current limits unknown')
    uncounted = [r['id'] for r in reviews if r['counts'] is None]
    return {'epic': epic, 'hours': hours, 'roles': roles, 'boundaries': boundaries,
            'reviews': reviews, 'consults': consults, 'unknown': unknown, 'not_counted': uncounted}


def render(data):
    def number(v):
        return 'unknown' if v is None else f'{v:.2f}'
    lines = [f"What it took — Epic {data['epic']}; hours: {number(data['hours'])}",
             'Role | asks | observed models/efforts | minutes']
    for role, row in sorted(data['roles'].items()):
        lines.append(f"{role} | {row['asks']} | {', '.join(row['agents'])} | {number(row['minutes'])}")
    lines.append('Boundary | limit | used / in force')
    for boundary, row in sorted(data['boundaries'].items()):
        for name, use in sorted(row.items()):
            lines.append(f"{boundary} | {name} | {number(use['used'])} / {number(use.get('limit'))} ({use.get('per', 'unknown')})")
    for review in data['reviews']:
        lines.append(f"review {review['id']}: " + (json.dumps(review['counts']) if review['counts'] else 'not counted'))
    for consult in data['consults']:
        lines.append(f"consult {consult['id']}: {consult['outcome'] or 'unknown'}")
    lines.extend('unknown: ' + item for item in data['unknown'])
    return '\n'.join(lines)


def effective_limits(needs, ledger):
    """Reuse the ledger's effective rounds, including the owner's go-scoped restriction."""
    from spend_ledger import DEFAULT_LIMITS, latest_go, rounds_allowed
    if needs['state'] != 'GO' and not needs.get('floor'):
        return None
    limits = (needs.get('parsed') or {}).get('limits') or (DEFAULT_LIMITS if not needs.get('allowances') else None)
    if limits is None or ledger is None:
        return None
    fields = needs.get('parsed') if needs.get('allowances') else None
    rounds = rounds_allowed(ledger, latest_go(ledger), fields)
    return {**limits, 'repair_rounds': {'limit': rounds, 'per': 'boundary'}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('epic', type=int)
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    errors = []
    try:
        body = (args.project / '.dev-auto/handoff.md').read_text()
    except OSError:
        body = ''
        errors.append('handoff unknown')
    budget = re.search(r'\b[0-9a-f]{16}-epic-' + str(args.epic) + r'\b', body)
    base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'dev-auto/budgets'
    ledger = read_json(base / f'{budget[0]}.json', errors) if budget else None
    limits = None
    try:
        import run_needs
        needs = run_needs.run_needs(args.project, args.epic)
        limits = effective_limits(needs, ledger)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        errors.append(f'limits: {type(exc).__name__}')
    runs = Path.home() / '.config/bmn/agents/state/team/runs'
    data = summarize(args.epic, body, ledger, runs, limits=limits)
    data['unknown'] = errors + data['unknown']
    print(json.dumps(data, indent=2) if args.json else render(data))
    return int(args.check and bool(data['unknown'] or data['not_counted']))


if __name__ == '__main__':
    raise SystemExit(main())
