#!/usr/bin/env python3
"""Offline signal, guard, proposal and CLI tests for flavor-suggest.py; run in CI."""
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('flavor_suggest', Path(__file__).resolve().parents[3] / 'scripts' / 'flavor-suggest.py')
fs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fs)


class SuggestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = [dict(repo='acme/app', pr=i, merged_at=f'2026-10-{11+i:02d}T00:00:00Z',
                          flavor='standard', changes_verdicts=0, reopened='',
                          escaped_defects=0, engine_runs=2, open_to_merge_min=100,
                          flavor_scope='project') for i in range(1, 21)]
        self.cards = []
        self.defects = []

    def run_cli(self, *extra):
        path = self.root / 'prs.csv'
        with path.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=self.rows[0].keys())
            w.writeheader()
            w.writerows(self.rows)
        for name, value in [('feedback', self.cards), ('defects', self.defects)]:
            (self.root / (name + '.json')).write_text(json.dumps(value))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fs.main(['--csv', str(path), '--repo', 'acme/app', '--flavor', 'standard',
                            '--as-of', '2026-11-01', '--last-change', '2026-09-01',
                            '--feedback', str(self.root / 'feedback.json'),
                            '--defects', str(self.root / 'defects.json'), *extra])
        return code, out.getvalue(), err.getvalue()

    def test_r1_and_owner_default(self):
        code, out, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn('standard → fast', out)
        self.assertIn('R1 as of', out)
        self.assertIn('Default if unanswered: keep standard', out)
        self.assertIn('Validator: pending', out)

    def test_t1_discovery_dates_override_old_merge(self):
        self.defects = [dict(repo='acme/app', date='2026-10-30', link='acme/app#90')]*2
        _, out, _ = self.run_cli('--metrics-gate-open', '--last-change', '2026-10-31')
        self.assertIn('T1 as of', out)
        self.assertIn('standard → thorough', out)
        self.assertNotIn('R1 as of', out)

    def test_t2_no_time_window(self):
        self.cards = [dict(repo='acme/app', date='2026-09-02', **{'class': 'missed-bug'}, link='card')]
        self.assertIn('T2 as of', self.run_cli()[1])

    def test_t3_boundary_and_minimum(self):
        self.rows = self.rows[-5:]
        self.rows[0]['reopened'] = 'reopened'
        self.assertIn('NONE:', self.run_cli()[1])
        self.rows[1]['changes_verdicts'] = 3
        self.assertIn('T3 as of', self.run_cli()[1])
        self.rows = self.rows[-4:]
        self.assertIn('NONE:', self.run_cli()[1])

    def test_rework_uses_current_flavor_cap(self):
        self.rows = self.rows[-5:]
        for r in self.rows:
            r['flavor'] = 'fast'
        self.rows[0]['changes_verdicts'] = 2
        self.rows[1]['changes_verdicts'] = 2
        self.assertIn('T3 as of', self.run_cli('--flavor', 'fast')[1])

    def test_r2_and_escaped_guard(self):
        self.rows = self.rows[-2:]
        for kind in ['too-slow', 'too-costly']:
            self.cards = [dict(repo='acme/app', date='2026-10-30', **{'class': kind}, link='card')]
            self.assertIn('R2 as of', self.run_cli()[1])
        self.defects = [dict(repo='acme/app', date='2026-10-30', link='defect')]
        self.assertIn('NONE:', self.run_cli()[1])

    def test_r3_speed_and_cost_and_quality(self):
        for i, r in enumerate(self.rows):
            r['merged_at'] = ('2026-10-10' if i < 10 else '2026-10-30') + 'T00:00:00Z'
            r['open_to_merge_min'] = 100 if i < 10 else 131
            r['engine_runs'] = 2 if i < 10 else 3
            r['changes_verdicts'] = 1
        for goal in ['speed', 'cost']:
            self.assertIn('R3 as of', self.run_cli('--goal', goal)[1])
        self.assertIn('NONE:', self.run_cli()[1])
        for r in self.rows[10:]:
            r['open_to_merge_min'] = 130
        self.assertIn('NONE:', self.run_cli('--goal', 'speed')[1])

    def test_relax_guards(self):
        for flags in [('--metrics-gate-open',), ('--last-change', '2026-10-10')]:
            self.assertIn('NONE:', self.run_cli(*flags)[1])
        self.assertIn('R1 as of', self.run_cli('--last-change', '2026-10-04')[1])
        self.assertIn('NONE:', self.run_cli('--defects', '')[1])

    def test_decline_cooldown_and_worse(self):
        decline = self.root / 'decline.json'
        decline.write_text(json.dumps(dict(date='2026-10-30', signals={'R1': 20})))
        self.assertIn('NONE:', self.run_cli('--declined', str(decline))[1])
        decline.write_text(json.dumps(dict(date='2026-10-04', signals={'R1': 20})))
        self.assertIn('R1 as of', self.run_cli('--declined', str(decline))[1])
        decline.write_text(json.dumps(dict(date='2026-10-30', signals={'T1': 2})))
        self.defects = [dict(repo='acme/app', date='2026-10-30', link='bug')]*3
        self.assertIn('T1 as of', self.run_cli('--declined', str(decline))[1])

    def test_scope_and_flavor_isolation(self):
        for r in self.rows:
            r['flavor_scope'] = 'docs/**'
        self.assertIn('NONE:', self.run_cli()[1])
        self.assertIn('R1 as of', self.run_cli('--scope', 'docs/**')[1])
        for r in self.rows:
            r['flavor'] = 'thorough'
        self.assertIn('NONE:', self.run_cli('--scope', 'docs/**')[1])

    def test_solo_preserves_builder_and_bounds(self):
        for r in self.rows:
            r['flavor'] = 'solo'
        self.assertIn('builder = "solo"', self.run_cli('--flavor', 'solo')[1])
        for r in self.rows:
            r['flavor'] = 'fast'
        self.assertIn('NONE:', self.run_cli('--flavor', 'fast')[1])
        for r in self.rows:
            r['flavor'] = 'thorough'
        self.cards = [dict(repo='acme/app', date='2026-10-30', **{'class': 'missed-bug'}, link='card')]
        self.assertIn('NONE:', self.run_cli('--flavor', 'thorough')[1])

    def test_custom_single_steps_preserve_merge_diversity(self):
        knobs = self.root / 'knobs.json'
        old = dict(zip(fs.ORDER, fs.PRESETS['standard']))
        knobs.write_text(json.dumps(old))
        for r in self.rows:
            r['flavor'] = 'custom'
        self.cards = [dict(repo='acme/app', date='2026-10-30', **{'class': 'too-costly'}, link='card')]
        out = self.run_cli('--flavor', 'custom', '--knobs', str(knobs))[1]
        self.assertIn('caps [3, 3] → [2, 2]', out)
        self.assertNotIn('merge =', out)
        self.assertNotIn('diversity =', out)
        self.assertNotIn('base =', out)

    def test_custom_asymmetric_caps_and_class_proposal(self):
        knobs = self.root / 'knobs.json'
        old = dict(zip(fs.ORDER, fs.PRESETS['standard']))
        old['caps'] = [3, 1]
        knobs.write_text(json.dumps(old))
        for r in self.rows:
            r['flavor'] = 'custom'
            r['flavor_scope'] = 'docs/**'
        self.cards = [dict(repo='acme/app', scope='docs/**', date='2026-10-30',
                           **{'class': 'too-costly'}, link='card')]
        code, out, _ = self.run_cli('--flavor', 'custom', '--scope', 'docs/**', '--knobs', str(knobs))
        self.assertEqual(code, 0)
        self.assertIn('caps [3, 1] → [2, 1]', out)
        self.assertIn('[[flavor.classes]]', out)
        self.assertNotIn('[flavor]\nname', out)

    def test_defect_window_boundaries(self):
        self.rows = self.rows[-2:]
        self.cards = [dict(repo='acme/app', date='2026-10-30', **{'class': 'too-slow'}, link='card')]
        self.defects = [dict(repo='acme/app', date='2026-10-02', link='old'),
                        dict(repo='acme/app', date='2026-11-02', link='future')]
        self.assertIn('R2 as of', self.run_cli()[1])
        self.defects.append(dict(repo='acme/app', date='2026-10-03', link='in-window'))
        self.assertIn('NONE:', self.run_cli()[1])

    def test_input_errors_no_traceback(self):
        self.rows[0]['engine_runs'] = 'nan'
        code, _, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn('invalid metric', err)
        self.assertNotIn('Traceback', err)

    def test_missing_extended_columns(self):
        for r in self.rows:
            del r['escaped_defects']
        self.assertEqual(self.run_cli()[0], 2)

    def test_future_and_wrong_repo_feedback_do_not_fire(self):
        self.rows = self.rows[-2:]
        self.cards = [dict(repo='acme/other', date='2026-10-30', **{'class': 'missed-bug'}, link='card'),
                      dict(repo='acme/app', date='2026-11-02', **{'class': 'missed-bug'}, link='card')]
        self.assertIn('NONE:', self.run_cli()[1])


if __name__ == '__main__':
    unittest.main()
