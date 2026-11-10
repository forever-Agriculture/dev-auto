# MODULE: lead_bench_record.py - consistency check for declared lead-run desktop QA evidence (not hostile-writer authentication)
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re


def document(path):
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Lead bench JSON exceeds 2 MiB')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Lead bench JSON must be an object')
    return value


def checked_lead_record(root):
    root = Path(os.path.abspath(root))
    if root.resolve() != root:
        raise ValueError('Lead bench record folder contains a symlink')
    def local(name):
        if not isinstance(name, str) or not name or '\\' in name or name.startswith('/') or any(p in ['', '.', '..'] for p in name.split('/')):
            raise ValueError('Lead bench evidence path escapes its record folder')
        path = root
        for part in name.split('/'):
            path /= part
            if path.is_symlink():
                raise ValueError('Lead bench evidence contains a symlink')
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError('Lead bench evidence file is missing or foreign')
        return path
    receipt = document(local('lead-bench.json'))
    required = {'version', 'route', 'executor', 'runId', 'finishedAt', 'input', 'brief', 'report', 'seed', 'actions', 'screenshots', 'state', 'completion', 'launches'}
    if set(receipt) != required or receipt.get('version') != 1 or receipt.get('route') != 'lead-bench' or receipt.get('executor') != 'lead':
        raise ValueError('Unsupported lead bench receipt route or version')
    run_id = receipt.get('runId')
    if not isinstance(run_id, str) or not re.fullmatch(r'\d+-[a-f0-9]{16}', run_id):
        raise ValueError('Lead bench generation is invalid')
    def artifact(reference):
        if not isinstance(reference, dict) or set(reference) != {'path', 'bytes', 'sha256', 'runId'} or reference['runId'] != run_id:
            raise ValueError('Lead bench evidence belongs to a foreign generation')
        path = local(reference['path'])
        if type(reference['bytes']) is not int or not 0 < reference['bytes'] <= 256 * 1024 * 1024 or path.stat().st_size != reference['bytes']:
            raise ValueError('Lead bench evidence size changed or is empty')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != reference['sha256']:
            raise ValueError('Lead bench evidence hash changed')
        return path
    if receipt['brief'].get('path') != 'qa/brief.json' or receipt['report'].get('path') != 'qa/report.json':
        raise ValueError('Lead bench brief/report must use the shared checker paths')
    files = {key: artifact(receipt[key]) for key in ['input', 'brief', 'report', 'seed', 'actions', 'state', 'completion']}
    binding, brief, report, state, completion = [document(files[key]) for key in ['input', 'brief', 'report', 'state', 'completion']]
    if binding.get('version') != 1 or binding.get('runId') != run_id or binding.get('route') != 'lead-bench' or binding.get('executor') != 'lead':
        raise ValueError('Lead bench reservation is foreign or invalid')
    if (brief.get('version') != 1 or brief.get('mode') != 'quick-bench' or brief.get('accounts', []) or
        binding.get('target') != 'bmn-bench:' + run_id or any(brief.get(k) != binding.get(k) or report.get(k) != binding.get(k) for k in ['target', 'revision'])):
        raise ValueError('Lead bench brief/report differs from its reserved candidate or target')
    if binding.get('briefSha256') != receipt['brief']['sha256']:
        raise ValueError('Lead bench brief differs from the pre-run reservation')
    candidate = binding.get('candidateSha256')
    fixture = binding.get('fixture')
    if (not isinstance(candidate, str) or not re.fullmatch(r'[a-f0-9]{64}', candidate) or not isinstance(fixture, dict) or
        not fixture.get('id') or fixture.get('seedSha256') != receipt['seed']['sha256'] or
        state.get('runId') != run_id or state.get('status') != 'stopped' or state.get('candidateSha256') != candidate or state.get('qaInput') != binding):
        raise ValueError('Lead bench candidate, fixture or inputs differ from the actual bench reservation')
    started, finished = [datetime.fromisoformat(value.replace('Z', '+00:00')) for value in [binding['startedAt'], receipt['finishedAt']]]
    if started.tzinfo is None or finished.tzinfo is None or finished < started:
        raise ValueError('Lead bench completion precedes its bound start')
    if any(completion.get(k) is not True for k in ['stopped', 'rootsDeleted', 'groupRemoved']):
        raise ValueError('Lead bench cleanup is incomplete')
    launches = receipt['launches']
    if not isinstance(launches, list) or not launches or {x.get('role') for x in launches} != {'workload', 'recovery'}:
        raise ValueError('Lead bench workload or recovery evidence is missing')
    keys = [x['key'] for x in launches]
    if len(set(keys)) != len(keys) or any(not re.fullmatch(r'[a-f0-9]{16}', key) for key in keys):
        raise ValueError('Lead bench launch keys are invalid or repeated')
    retained = {row['key']: row for row in state['tracers']}
    completed = {row['key']: row for row in completion['traces']}
    if set(keys) != set(retained) or len(state['tracers']) != len(keys) or set(keys) != set(completed) or len(completion['traces']) != len(keys):
        raise ValueError('Lead bench omitted or borrowed a workload/recovery launch')
    allowed = {receipt[k]['path'] for k in ['actions', 'state', 'completion']}
    if not isinstance(receipt['screenshots'], list) or not receipt['screenshots']:
        raise ValueError('Lead bench screenshot evidence is missing')
    for shot in receipt['screenshots']:
        artifact(shot); allowed.add(shot['path'])
    for launch in launches:
        identity = launch.get('identity')
        if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or identity['pid'] <= 0 or
            not re.fullmatch(r'[1-9]\d*', str(identity.get('start_ticks', ''))) or retained[launch['key']].get('identity') != identity or
            retained[launch['key']].get('role') != launch['role'] or completed[launch['key']].get('complete') is not True):
            raise ValueError('Lead bench launch identity or capture completion is invalid')
        artifact(launch['trace']); cert = document(artifact(launch['certificate']))
        if (cert.get('runId') != run_id or cert.get('launchKey') != launch['key'] or cert.get('role') != launch['role'] or
            cert.get('traceBytes') != launch['trace']['bytes'] or cert.get('traceSha256') != launch['trace']['sha256'] or cert.get('traceErrors') != []):
            raise ValueError('Lead bench trace differs from its retained capture certificate')
        allowed.update([launch['trace']['path'], launch['certificate']['path']])
    actions = [json.loads(line) for line in files['actions'].read_text().splitlines() if line.strip()]
    if not actions or any(row.get('runId') != run_id for row in actions):
        raise ValueError('Lead bench actions are missing or from another generation')
    names = {name for row in report['criteria'] + report['findings'] for name in row['evidence']}
    if not names or not names.issubset(allowed):
        raise ValueError('Lead bench report names evidence absent from the retained capture')
    return brief, report


def lead_candidate(root):
    """What an admitted lead bench run loaded: its candidate bytes and its fixture seed (call after checked_lead_record)."""
    root = Path(os.path.abspath(root))
    binding = document(root / document(root / 'lead-bench.json')['input']['path'])
    return binding['candidateSha256'], binding['fixture']['seedSha256']
