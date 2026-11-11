# MODULE: test_scorecard.py - exact synthetic counts and metadata-only reads
from datetime import datetime, timezone
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/dev-auto/scripts'))
import scorecard


class ScorecardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runs = self.root / 'asks'
        self.runs.mkdir()
        self.body = '- Run checkouts: ["/fixture/run", "/fixture/companion"]\n- Run started: 2026-11-11T10:00:00Z\n- Run finished: 2026-11-11T12:00:00Z\n'
        self.ledger = {'epic': 7, 'uses': {'one': {'answer': 'TAKEN', 'boundary': '7.1', 'limit': 'full_reviews', 'amount': 1, 'value': 2, 'per': 'boundary'},
                        'two': {'answer': 'REFUSED', 'boundary': '7.1', 'limit': 'full_reviews', 'amount': 1}},
                       'rounds': {'r': {'answer': 'TAKEN', 'boundary': '7.1'}}}
        self.limits = {'full_reviews': {'limit': 2, 'per': 'boundary'}, 'repair_rounds': {'limit': 4, 'per': 'boundary'}, 'consults': {'limit': 2, 'per': 'epic'}}

    def ask(self, rid, role='epic-reviewer', project='/fixture/run', phase='initial', at='2026-11-11T10:30:00Z'):
        d = self.runs / rid
        d.mkdir()
        (d / 'request.json').write_text(json.dumps({'id': rid, 'project': project, 'role': role, 'phase': phase, 'asked_at': at}))
        (d / 'outcome.json').write_text(json.dumps({'observed': {'model': 'fixture', 'effort': 'high'}, 'started_at': at, 'ended_at': '2026-11-11T10:40:00Z'}))
        for f in ('question.md', 'answer.md', 'transcript.jsonl'):
            (d / f).write_text('MUST NEVER READ')
        return d

    def summarize(self):
        return scorecard.summarize(7, self.body, self.ledger, self.runs, limits=self.limits)

    def test_exact_counts_scope_and_metadata_only(self):
        (self.runs / '.keys').mkdir()
        (self.runs / '.places').mkdir()
        self.ask('full')
        self.ask('recheck', project='/fixture/companion', phase='recheck')
        self.ask('consult', role='consultant')
        self.ask('elsewhere', project='/fixture/unrelated')
        self.ask('earlier', at='2026-11-11T09:30:00Z')
        self.ask('later', at='2026-11-11T13:00:00Z')
        self.body += '- review full: 3 findings, 2 repaired, 1 rejected, 0 deferred\n- review recheck: 0 findings, 0 repaired, 0 rejected, 0 deferred\n- consult: unblocked, method worked\n'
        opened = []
        original = Path.open
        def traced(path, *args, **kwargs):
            opened.append(path.name)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', traced):
            data = self.summarize()
        self.assertFalse(set(opened) & {'question.md', 'answer.md', 'transcript.jsonl'})
        self.assertEqual(data['hours'], 2)
        self.assertEqual(data['roles']['epic-reviewer'], {'asks': 2, 'agents': ['fixture/high'], 'minutes': 20})
        self.assertEqual(data['boundaries']['7.1']['full_reviews']['used'], 1)
        self.assertEqual(data['boundaries']['7.1']['repair_rounds'], {'used': 1, 'limit': 4, 'per': 'boundary'})
        full = next(r for r in data['reviews'] if r['id'] == 'full')
        self.assertEqual(full['counts']['repaired'], 2)
        self.assertEqual(data['consults'], [{'id': 'consult', 'outcome': 'unblocked'}])
        self.assertEqual(data['unknown'], [])
        self.assertEqual(data['not_counted'], [])
        self.assertEqual(json.loads(json.dumps(data)), data)
        self.assertIn('fixture/high | 20.00', scorecard.render(data))

    def test_missing_review_and_optional_consult_outcome(self):
        self.ask('full')
        self.ask('consult', role='consultant')
        data = self.summarize()
        self.assertEqual(data['not_counted'], ['full'])
        self.assertIn('not counted', scorecard.render(data))
        self.assertIsNone(data['consults'][0]['outcome'])
        self.assertEqual(data['unknown'], [])

    def test_missing_and_unreadable_records_stay_unknown(self):
        d = self.ask('full')
        (d / 'outcome.json').unlink()
        data = self.summarize()
        self.assertIsNone(data['roles']['epic-reviewer']['minutes'])
        self.assertIn('unknown', scorecard.render(data))
        (d / 'request.json').write_text('{broken')
        self.assertTrue(self.summarize()['unknown'])
        self.assertTrue(scorecard.summarize(7, '', None, self.root/'missing')['unknown'])

    def test_inconsistent_and_duplicate_findings_are_unknown(self):
        self.ask('full')
        self.body += '- review full: 1 findings, 2 repaired, 0 rejected, 0 deferred\n'
        self.assertTrue(self.summarize()['unknown'])
        self.body += '- review full: 0 findings, 0 repaired, 0 rejected, 0 deferred\n'
        self.assertTrue(self.summarize()['unknown'])

    def test_missing_ledger_sections_and_bad_route_are_unknown(self):
        d = self.ask('full')
        data = json.loads((d / 'outcome.json').read_text())
        data['observed'] = ['bad shape']
        (d / 'outcome.json').write_text(json.dumps(data))
        self.ledger.pop('uses')
        self.assertIn('ledger uses unknown', self.summarize()['unknown'])
        self.assertTrue(any('route unknown' in x for x in self.summarize()['unknown']))

    def test_cli_unknowns_are_nonfatal_until_check(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, patch('run_needs.run_needs', return_value={'state': 'NO_GO_RECORD'}), patch.object(Path, 'home', return_value=self.root):
            self.assertEqual(scorecard.main(['7', '--project', str(self.root)]), 0)
            self.assertEqual(scorecard.main(['7', '--project', str(self.root), '--json', '--check']), 1)
        self.assertIn('unknown', out.getvalue())

    def test_epic_uses_aggregate_across_stories_like_ledger(self):
        from spend_ledger import limit_used
        for boundary in ('7.1', '7.2', 'epic'):
            self.ledger['uses'][boundary] = {'answer':'TAKEN','boundary':boundary,'limit':'consults','amount':1,'value':3,'per':'epic'}
        self.ledger['uses']['refused'] = {'answer':'REFUSED','boundary':'7.2','limit':'consults','amount':1}
        data = self.summarize()
        self.assertEqual(data['boundaries']['epic']['consults']['used'], limit_used(self.ledger,'consults'))
        self.assertEqual(data['boundaries']['epic']['consults']['used'], 3)
        self.assertNotIn('consults', data['boundaries']['7.1'])

    def test_partial_entries_never_crash_or_become_zero_and_cli_check_fails(self):
        for corrupt in (None, {}, {'answer':'TAKEN','boundary':'7.1','limit':'consults','per':'epic'}):
            with self.subTest(corrupt=corrupt):
                self.ledger['uses']['bad'] = corrupt
                data = self.summarize()
                self.assertIsNone(data['boundaries']['epic']['consults']['used'])
                self.assertIn('ledger uses unknown', data['unknown'])
                self.assertIn('unknown', scorecard.render(data))
        d=self.ask('empty');(d/'request.json').write_text('{}')
        self.assertTrue(any('request metadata unknown' in x for x in self.summarize()['unknown']))
        # CLI text and JSON both survive partial real files and fail only with --check.
        state=self.root/'.dev-auto';state.mkdir()
        (state/'handoff.md').write_text(self.body+'- Budget id: abcdef0123456789-epic-7\n')
        budget=self.root/'state/dev-auto/budgets';budget.mkdir(parents=True)
        (budget/'abcdef0123456789-epic-7.json').write_text(json.dumps(self.ledger))
        with patch.dict('os.environ', {'XDG_STATE_HOME':str(self.root/'state')}), patch('run_needs.run_needs', return_value={'state':'GO','parsed':{},'allowances':None}), patch.object(Path,'home',return_value=self.root), patch.object(scorecard,'effective_limits',return_value=self.limits):
            for flags in ([],['--json']):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(scorecard.main(['7','--project',str(self.root),*flags]),0)
                self.assertIn('unknown',out.getvalue())
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(scorecard.main(['7','--project',str(self.root),*flags,'--check']),1)

    def test_round_limit_and_expiry_reuse_ledger_calculation(self):
        from spend_ledger import rounds_allowed
        old={'kind':'go','commit':'a'*40,'rounds':4,'allowances':True}
        self.ledger.update(gos=[old], round_limit={'go':old['commit'],'rounds':1})
        needs={'state':'GO','allowances':True,'parsed':{'rounds':4,'limits':self.limits}}
        self.assertEqual(scorecard.effective_limits(needs,self.ledger)['repair_rounds']['limit'],rounds_allowed(self.ledger,old,needs['parsed']))
        self.assertEqual(scorecard.effective_limits(needs,self.ledger)['repair_rounds']['limit'],1)
        self.ledger['gos'].append({**old,'commit':'b'*40})
        self.assertEqual(scorecard.effective_limits(needs,self.ledger)['repair_rounds']['limit'],4)
        self.assertIsNone(scorecard.effective_limits({'state':'NO_GO_RECORD','unconfirmed':True},self.ledger))

    def test_money_uses_settled_and_committed_ledger_jobs(self):
        self.limits['money_usd']={'limit':10,'per':'epic'}
        self.ledger['jobs']={'a':{'state':'settled','spent':2}, 'b':{'state':'reserved','max':3},'c':{'state':'released','max':4}}
        self.assertEqual(self.summarize()['boundaries']['epic']['money_usd']['used'],5)
        self.ledger['jobs']['bad']=None
        self.assertIsNone(self.summarize()['boundaries']['epic']['money_usd']['used'])

    def test_account_wide_null_project_asks_are_unrelated_not_unknown(self):
        self.ask('account-wide',project=None)
        self.assertEqual(self.summarize()['unknown'],[])
        self.assertEqual(self.summarize()['roles'],{})
