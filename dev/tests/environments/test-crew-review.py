"""Review command process tests reuse the shipped pool's fake engine/backend lifecycle.

Checks explicit head/round handoff, duplicate suppression, fresh validation and actual builder engine exclusion.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

spec = importlib.util.spec_from_file_location("review_pool_fixture", Path(__file__).with_name("test-crew-reviewer-pool.py"))
pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pool)


class Review(pool.ReviewerPool):
    def command(self, command='review', *extra):
        return self.crew(command, '12', '--head', self.sha, '--round', '1', '--project', self.project, '--timeout', '1', *extra)

    def test_explicit_handoff_fresh_passes_engine_exclusion_and_duplicates(self):
        first = self.command()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(self.command().returncode, 0)
        self.assertEqual(len(self.messages()), 1)
        self.pool()
        review = self.record('vera-12-r1-review')
        self.assertNotEqual(review['engine'], 'codex')
        self.assertEqual(review['head'], self.sha)
        self.assertEqual(self.command().returncode, 0)
        self.assertEqual(len(self.messages()), 0)
        self.put('verdicts/pr12-%s-r1-review.md' % self.sha[:7], 'review output')
        self.put('status/vera-12-r1-review.status', 'done: #12 %s review pass\n' % self.sha)
        self.queue(self.status('vera-12-r1-review', 'review pass'))
        self.route()
        self.pool()
        validation = self.record('vera-12-r1-validate')
        self.assertNotEqual(validation['engine'], 'codex')
        self.assertNotEqual(validation['worktree'], review['worktree'])
        self.assertNotIn('vera-12-r1-review', self.names())
        self.assertIn('vera-12-r1-validate', self.names())

    def test_refused_head_round_hold_pause_has_no_handoff(self):
        for extra in (('--head', 'short'), ('--head', 'f' * 40), ('--round', '0'), ('--round', '2')):
            self.assertNotEqual(self.command('review', *extra).returncode, 0)
        for patch in ({'isDraft': True}, {'state': 'CLOSED'}, {'labels': [{'name': 'crew:hold'}]},
                      {'labels': [{'name': 'crew:escalated'}]}):
            old = dict(self.live)
            self.live.update(patch)
            self.save()
            self.assertNotEqual(self.command().returncode, 0)
            self.live = old
        self.save()
        self.put('pause.json', '{"since":"now"}')
        self.assertNotEqual(self.command().returncode, 0)
        self.assertEqual(self.messages(), [])
        self.assertNotIn('vera-lead', self.names())

    def test_linked_item_hold_refuses(self):
        self.live['_issue'] = {'labels': [{'name': 'crew:hold'}]}
        self.save()
        self.assertNotEqual(self.command().returncode, 0)
        self.assertEqual(self.messages(), [])

    def test_reset_allows_new_round_one_at_same_head(self):
        self.live['reviews'] = [self.signed('<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=1 verdict=changes -->' % self.sha),
                                self.signed('<!-- crew:v1 role=coordinator pass=steer cmd=resume sha=%s -->' % self.sha, 'acme-bot', 'Ash')]
        self.save()
        r = self.command()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.messages()), 1)

    def test_completed_review_and_rereview_binding(self):
        self.live['reviews'] = [self.signed('<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=1 verdict=pass -->' % self.sha)]
        self.save()
        r = self.command()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('already completed', r.stdout)
        self.assertEqual(self.messages(), [])
        self.live['reviews'].append(self.signed('<!-- crew:v1 role=coordinator pass=steer cmd=rereview cmd-id=fresh sha=%s -->' % self.sha, 'acme-bot', 'Ash'))
        self.save()
        self.assertNotEqual(self.command().returncode, 0)
        r = self.command('review', '--rereview-id', 'fresh')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.messages()[0]['refs'], ['#12', self.sha, '1', 'fresh'])

    def test_admission_defers_and_releases_capacity(self):
        self.gate('max_load = 4')
        self.assertEqual(self.spawn('reviewer', '--pr', '12', '--round', '3').returncode, 0)
        self.target(4)
        self.assertEqual(self.command().returncode, 0)
        self.pool(load=4)
        self.assertNotIn('vera-12-r1-review', self.names())
        self.assertEqual(len(self.messages()), 1)
        self.pool(load=0)
        self.assertIn('vera-12-r1-review', self.names())

    def test_ownership_refusal_has_no_handoff(self):
        path = Path(self.project)
        path.write_text(path.read_text().replace('[repo]', '[repo]\ncontrol_item = 1').replace('[runtime]', '[runtime]\ninstance = "test"'))
        r = self.command()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.messages(), [])
        self.assertNotIn('vera-lead', self.names())


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Review(name) for name in Review.__dict__ if name.startswith('test_'))


if __name__ == '__main__':
    unittest.main()
