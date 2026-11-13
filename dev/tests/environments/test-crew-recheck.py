"""Explicit recheck command process tests: approved two-parent merges, round retention and full-review escalation."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("review_command_fixture", Path(__file__).with_name("test-crew-review.py"))
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class Recheck(review.Review):
    def approved(self, round_=1):
        old = 'a' * 40
        self.live['reviews'] = [self.signed('<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=%s verdict=pass -->' % (old, round_))]
        self.live['_parents'] = [{'sha': old}, {'sha': 'b' * 40}]
        self.live['_comparison'] = 'identical'
        self.save()

    def test_explicit_merge_recheck_keeps_approval_round(self):
        self.approved(round_=2)
        r = self.command('recheck', '--round', '2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.messages()[0]['kind'], 'recheck')
        self.assertEqual(self.messages()[0]['refs'], ['#12', self.sha, '2'])
        self.pool()
        self.assertIn('vera-12-r2-recheck', self.names())
        self.assertNotIn('vera-12-r2-validate', self.names())

    def test_unconfirmed_merge_and_open_rereview_use_normal_review(self):
        r = self.command('recheck')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('escalates to normal review', r.stdout)
        self.assertEqual(self.messages()[0]['kind'], 'review')
        self.approved()
        self.live['reviews'].append(self.signed('<!-- crew:v1 role=coordinator pass=steer cmd=rereview cmd-id=fresh sha=%s -->' % self.sha, 'acme-bot', 'Ash'))
        self.save()
        r = self.command('recheck', '--rereview-id', 'fresh')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.messages()[-1]['kind'], 'review')

    def test_recheck_wrong_round_and_held_have_no_effect(self):
        self.approved(round_=2)
        self.assertEqual(self.command('recheck').returncode, 2)
        self.live['labels'] = [{'name': 'crew:hold'}]
        self.save()
        self.assertEqual(self.command('recheck', '--round', '2').returncode, 2)
        self.assertEqual(self.messages(), [])

    def test_non_default_second_parent_escalates(self):
        self.approved()
        self.live['_comparison'] = 'diverged'
        self.save()
        r = self.command('recheck')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.messages()[0]['kind'], 'review')


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Recheck(name) for name in Recheck.__dict__ if name.startswith('test_'))


if __name__ == '__main__':
    unittest.main()
