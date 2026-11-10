# MODULE: test_lead_bench_gate.py - honest lead-run evidence binding, capture completeness and retest contracts
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_qa_gate as native

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/dev-auto/scripts/qa_gate.py'
RUN = '1794160000000-0123456789abcdef'
TARGET = 'bmn-bench:' + RUN

class LeadBenchTests(unittest.TestCase):
    setUp = native.QaGateTests.setUp
    write = native.QaGateTests.write
    load = native.QaGateTests.load
    finding = native.QaGateTests.finding

    def describe(self, root, name):
        raw = (root / name).read_bytes()
        return {'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'runId': RUN}

    def record(self, name='current', revision='candidate-2', verdict='GO', finding=None, prior=None, candidate=None, defect=None):
        root = self.root / name
        brief = {'version': 1, 'mode': 'quick-bench', 'revision': revision, 'target': TARGET,
                 'prior_findings': [] if prior is None else [{'finding': prior, 'disposition': 'Repair needs retest'}]}
        report = {'version': 1, 'mode': 'quick-bench', 'revision': revision, 'target': TARGET, 'verdict': verdict,
                  'goal_check': {'status': 'achieved' if verdict == 'GO' else 'not achieved', 'execution': 'started'},
                  'criteria': [{'id': 'AC1', 'evidence': ['bench/screen.png', 'bench/actions.jsonl']}],
                  'findings': [] if finding is None else [finding]}
        self.write(root, 'qa/brief.json', brief); self.write(root, 'qa/report.json', report)
        self.write(root, 'bench/seed.json', {'id': 'synthetic-seed-v1', 'defect': verdict == 'NO-GO' if defect is None else defect})
        binding = {'version': 1, 'runId': RUN, 'route': 'lead-bench', 'executor': 'lead', 'revision': revision, 'target': TARGET,
                   'candidateSha256': candidate or ('1' if revision == 'candidate-1' else '2') * 64,
                   'fixture': {'id': 'synthetic-seed-v1', 'seedSha256': self.describe(root, 'bench/seed.json')['sha256']},
                   'briefSha256': self.describe(root, 'qa/brief.json')['sha256'], 'startedAt': '2026-11-08T19:00:00Z'}
        self.write(root, 'bench/input.json', binding)
        (root / 'bench/actions.jsonl').write_text(json.dumps({'runId': RUN, 'at': '2026-11-08T19:01:00Z', 'args': ['screenshot', 'screen']}) + '\n')
        (root / 'bench/screen.png').write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')
        launches = []
        for n, role in enumerate(['workload', 'recovery']):
            key = str(n + 1) * 16
            trace = f'bench/{role}.strace'
            (root / trace).write_text(f'{100 + n} +++ exited with 0 +++\n')
            certificate = f'bench/{role}-certificate.json'
            self.write(root, certificate, {'version': 1, 'runId': RUN, 'launchKey': key, 'role': role,
                       'traceBytes': self.describe(root, trace)['bytes'], 'traceSha256': self.describe(root, trace)['sha256'],
                       'traceErrors': [], 'rawWaitStatus': 0, 'exitCode': 0, 'signal': None})
            launches.append({'key': key, 'role': role, 'identity': {'pid': 100 + n, 'start_ticks': '123'},
                             'trace': self.describe(root, trace), 'certificate': self.describe(root, certificate)})
        self.write(root, 'bench/state.json', {'runId': RUN, 'status': 'stopped', 'candidateSha256': binding['candidateSha256'],
                   'qaInput': binding, 'tracers': [{k: row[k] for k in ['key', 'role', 'identity']} for row in launches]})
        self.write(root, 'bench/completion.json', {'stopped': True, 'rootsDeleted': True, 'groupRemoved': True,
                   'traces': [{'key': row['key'], 'complete': True} for row in launches]})
        receipt = {'version': 1, 'route': 'lead-bench', 'executor': 'lead', 'runId': RUN, 'finishedAt': '2026-11-08T19:02:00Z',
                   'input': self.describe(root, 'bench/input.json'), 'brief': self.describe(root, 'qa/brief.json'),
                   'report': self.describe(root, 'qa/report.json'), 'seed': self.describe(root, 'bench/seed.json'),
                   'actions': self.describe(root, 'bench/actions.jsonl'), 'screenshots': [self.describe(root, 'bench/screen.png')],
                   'state': self.describe(root, 'bench/state.json'), 'completion': self.describe(root, 'bench/completion.json'), 'launches': launches}
        self.write(root, 'lead-bench.json', receipt)
        return root

    def invoke(self, root, revision='candidate-2', *extra):
        r = subprocess.run([sys.executable, str(SCRIPT), str(root), '--lead-bench', '--revision', revision,
                            '--target', TARGET, '--bmn', str(self.checker), *map(str, extra)], capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout) if r.stdout else {'status': 'invalid', 'reason': r.stderr}

    def update(self, root, artifact, mutation):
        value = self.load(root, artifact); mutation(value); self.write(root, artifact, value)
        receipt = self.load(root, 'lead-bench.json')
        for key in ['input', 'brief', 'report', 'seed', 'state', 'completion']:
            if receipt[key]['path'] == artifact: receipt[key] = self.describe(root, artifact)
        self.write(root, 'lead-bench.json', receipt)

    def test_honest_go_passes_and_readonly_resume_reuses_it(self):
        root = self.record(); before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        for _ in range(2): self.assertEqual(self.invoke(root)[1]['status'], 'pass')
        self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_honest_no_go_remains_blocked(self):
        self.assertEqual(self.invoke(self.record(verdict='NO-GO'))[1]['status'], 'blocked')

    def test_changed_brief_report_image_and_missing_trace_are_refused(self):
        for name in ['qa/brief.json', 'qa/report.json', 'bench/screen.png', 'bench/recovery.strace']:
            with self.subTest(name=name):
                root = self.record(name.replace('/', '-'))
                if name.endswith('strace'): (root / name).unlink()
                else: (root / name).write_bytes(b'changed')
                self.assertEqual(self.invoke(root)[1]['status'], 'invalid')

    def test_foreign_generation_and_omitted_recovery_never_pass(self):
        for kind in ['generation', 'omit', 'incomplete']:
            root = self.record(kind); receipt = self.load(root, 'lead-bench.json')
            if kind == 'generation': receipt['screenshots'][0]['runId'] = 'foreign'
            elif kind == 'omit': receipt['launches'].pop()
            else:
                self.update(root, 'bench/completion.json', lambda d: d['traces'][1].update(complete=False))
                receipt = self.load(root, 'lead-bench.json')
            self.write(root, 'lead-bench.json', receipt)
            self.assertEqual(self.invoke(root)[1]['status'], 'invalid')

    def test_relabelled_revision_target_candidate_or_seed_cannot_replace_reservation(self):
        for field in ['revision', 'target', 'candidateSha256', 'fixture']:
            root = self.record(field)
            self.update(root, 'bench/input.json', lambda d: d.update({field: {'id': 'other', 'seedSha256': 'f' * 64} if field == 'fixture' else 'other'}))
            self.assertEqual(self.invoke(root)[1]['status'], 'invalid')

    def test_symlink_and_escaping_evidence_paths_are_refused(self):
        for kind in ['symlink', 'escape']:
            root = self.record(kind); image = root / 'bench/screen.png'; outside = self.root / (kind + '.png'); outside.write_bytes(image.read_bytes())
            if kind == 'symlink': image.unlink(); image.symlink_to(outside)
            else:
                receipt = self.load(root, 'lead-bench.json'); receipt['screenshots'][0]['path'] = '../escape.png'; self.write(root, 'lead-bench.json', receipt)
            self.assertEqual(self.invoke(root)[1]['status'], 'invalid')

    def test_unsupported_report_evidence_and_shared_checker_failure_block(self):
        root = self.record()
        self.update(root, 'qa/report.json', lambda d: d['criteria'][0].update(evidence=['unretained.png']))
        self.assertEqual(self.invoke(root)[1]['status'], 'invalid')
        root = self.record('checker'); self.checker.write_text('#!/usr/bin/env python3\nraise SystemExit(1)\n')
        self.assertEqual(self.invoke(root)[1]['status'], 'invalid')

    def test_same_loaded_candidate_and_fixture_under_a_new_label_is_no_repair(self):
        original = self.finding(); prior = self.record('prior', 'candidate-1', 'NO-GO', original)
        old = lambda: json.loads(json.dumps(original))
        relabelled = self.record('relabelled', 'candidate-2', finding=self.finding(True, True), prior=old(), candidate='1' * 64, defect=True)
        result = self.invoke(relabelled, 'candidate-2', '--prior', prior, '--prior-lead-bench')[1]
        self.assertEqual(result['status'], 'invalid'); self.assertIn('same loaded candidate', result['reason'])
        for name, extra in [('new-bytes', {'defect': True}), ('new-fixture', {'candidate': '1' * 64})]:
            root = self.record(name, 'candidate-2', finding=self.finding(True, True), prior=old(), **extra)
            self.assertEqual(self.invoke(root, 'candidate-2', '--prior', prior, '--prior-lead-bench')[1]['status'], 'pass')

    def test_lead_prior_retest_uses_same_facts_and_repaired_candidate_rules(self):
        original = self.finding(); prior = self.record('prior', 'candidate-1', 'NO-GO', original)
        for kind in ['pass', 'same', 'missing', 'altered']:
            revision = 'candidate-1' if kind == 'same' else 'candidate-2'
            old = None if kind == 'missing' else json.loads(json.dumps(original))
            if kind == 'altered': old['severity'] = 'minor'
            root = self.record(kind, revision, finding=self.finding(True, True), prior=old)
            result = self.invoke(root, revision, '--prior', prior, '--prior-lead-bench')[1]
            self.assertEqual(result['status'], 'pass' if kind == 'pass' else 'invalid')
