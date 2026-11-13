"""Process tests of marker ack modes (#237), using fake gh and real temporary Git histories.

Accepted and refused calls assert exits and native COMMENT effects; no real forge writes.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crew_testlib import Base

FAKE = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
a = sys.argv[1:]
p = Path(os.environ['ACK_FAKE'])
d = json.loads(p.read_text())
if a[:2] == ['pr', 'view']:
    d['reads'] = d.get('reads', 0) + 1
    if os.environ.get('MOVE_HEAD') and d['reads'] > 1:
        d['pr']['headRefOid'] = 'f' * 40
    p.write_text(json.dumps(d))
    print(json.dumps(d['pr']))
elif a[:2] == ['api', 'user']:
    print(json.dumps({'login': os.environ.get('POST_LOGIN', d['login'])}))
elif a[:2] == ['issue', 'view']:
    print(json.dumps(d['issue']))
elif a[0] == 'api' and '/issues/comments/' in a[1]:
    print(json.dumps(d['source']))
elif a[0] == 'api' and '/reviews' in a[1]:
    body = Path(next(x[6:] for x in a if x.startswith('body=@'))).read_text()
    d['effects'].append({'argv': a, 'body': body})
    d['pr']['reviews'].append({'author': {'login': d['login']}, 'body': body})
    p.write_text(json.dumps(d))
    sys.exit(int(os.environ.get('LOSE_RESPONSE', '0')))
else:
    sys.exit(9)
'''


class Ack(Base):
    def git(self, *args):
        r = subprocess.run(['git', '-c', 'user.name=test', '-c', 'user.email=test', *args],
                           cwd=self.project_dir, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def save(self):
        self.data_path.write_text(json.dumps(self.data))
        self.run_path.write_text(json.dumps(self.rec))

    def setUp(self):
        super().setUp()
        self.git('init', '-q', '-b', 'main')
        self.git('commit', '-q', '--allow-empty', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/remotes/origin/main', self.base)
        self.git('switch', '-q', '-c', 'builder/7-test')
        Path(self.project_dir, 'feature').write_text('feature\n')
        self.git('add', 'feature')
        self.git('commit', '-q', '-m', 'feature\n\nEngine: codex gpt-6.1-sol medium')
        self.head = self.git('rev-parse', 'HEAD')
        self.actor = 'vera-9-r1-review'
        self.rec = {'role': 'reviewer', 'args': {'pr': 9, 'round': 1}, 'pass': 'review', 'head': self.head,
                    'worktree': self.project_dir, 'engine': 'claude-code', 'model': 'sonnet', 'effort': 'medium',
                    'harness': 'claude-code', 'start': '2026-11-13T00:00:00Z'}
        self.run_path = Path(self.state, 'runs', self.actor + '.json')
        self.run_path.parent.mkdir(parents=True)
        self.data_path = Path(self.tmp, 'fake.json')
        self.data = {'login': 'acme-reviewer', 'effects': [], 'pr': {
            'number': 9, 'state': 'OPEN', 'isDraft': False, 'headRefOid': self.head, 'baseRefName': 'main',
            'labels': [], 'reviews': [], 'commits': [], 'body': '', 'statusCheckRollup': [],
            'closingIssuesReferences': [{'number': 7}]}}
        self.env.update(CREW_ID=self.actor, CREW_ROLE='reviewer', ACK_FAKE=str(self.data_path))
        Path(self.tmp, 'bin', 'gh').write_text(FAKE)
        self.save()

    def ack(self, mode='intake', *extra, **env):
        return self.crew('ack', mode, '9', '--head', self.head, '--actor', self.actor,
                         '--project', self.project, *extra, **env)

    def effects(self):
        return json.loads(self.data_path.read_text())['effects']

    def refused(self, mode='intake', *extra, **env):
        r = self.ack(mode, *extra, **env)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('refusing', r.stdout)
        self.assertEqual(self.effects(), [])

    def test_intake_native_head_signature_and_duplicate(self):
        r = self.ack()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('posted COMMENT', r.stdout)
        effect = self.effects()[0]
        self.assertIn('commit_id=' + self.head, effect['argv'])
        self.assertIn('event=COMMENT', effect['argv'])
        self.assertIn('role=reviewer-validator pass=ack pr=9 sha=' + self.head, effect['body'])
        self.assertIn('round=n/a verdict=n/a', effect['body'])
        self.assertIn('— 🔎 Vera (Reviewer-validator) · claude-code · sonnet', effect['body'])
        self.assertIn('Run:', effect['body'])
        self.assertEqual(self.ack().returncode, 0)
        self.assertEqual(len(self.effects()), 1)

    def test_intake_phase_role_head_and_identity_refusals(self):
        for patch in ({'isDraft': True}, {'state': 'CLOSED'}, {'headRefOid': 'a' * 40},
                      {'labels': [{'name': 'crew:hold'}]}, {'labels': [{'name': 'crew:escalated'}]}):
            with self.subTest(patch=patch):
                old = dict(self.data['pr'])
                self.data['pr'].update(patch)
                self.save()
                self.refused()
                self.data['pr'] = old
        for patch in ({'pass': 'validate'}, {'args': {'pr': 9, 'round': 2}}, {'role': 'builder'},
                      {'engine': 'codex'}, {'head': 'b' * 40}, {'args': {'pr': 10, 'round': 1}}):
            with self.subTest(patch=patch):
                old = dict(self.rec)
                self.rec.update(patch)
                self.save()
                self.refused()
                self.rec = old
        self.save()
        self.refused(POST_LOGIN='other')
        self.refused('intake', '--head', 'abcdef0')

    def test_moves_between_reads_and_uncertain_response(self):
        self.refused(MOVE_HEAD='1')
        self.save()
        r = self.ack(LOSE_RESPONSE='1')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('confirmed by readback', r.stdout)
        self.assertEqual(len(self.effects()), 1)

    def test_precheck_missing_refuses(self):
        with open(self.project, 'a') as f:
            f.write('\n[builder.precheck]\nenabled = true\n')
        self.refused()

    def test_precheck_pass_and_wrong_item_binding(self):
        with open(self.project, 'a') as f:
            f.write('\n[builder.precheck]\nenabled = true\n')
        fields = ' '.join(name + '=pass' for name in ('rebase', 'lint', 'tests', 'build', 'self-review', 'docs', 'evidence'))
        self.data['pr']['body'] = '<!-- crew:v1 role=builder pass=precheck issue=8 sha=%s round=n/a verdict=n/a %s -->' % (self.head, fields)
        self.save()
        self.refused()
        self.data['pr']['body'] = self.data['pr']['body'].replace('issue=8', 'issue=7')
        self.save()
        r = self.ack()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_missing_required_inputs_have_no_effect(self):
        r = self.crew('ack', 'intake', '9', '--project', self.project)
        self.assertEqual(r.returncode, 2)
        self.assertIn('--head', r.stderr)
        self.assertEqual(self.effects(), [])

    def test_ownership_and_pause_refuse(self):
        Path(self.state, 'pause.json').write_text('{"since":"now"}')
        self.refused()
        Path(self.state, 'pause.json').unlink()
        path = Path(self.project)
        path.write_text(path.read_text().replace('[repo]', '[repo]\ncontrol_item = 1').replace('[runtime]', '[runtime]\ninstance = "test"'))
        self.refused()

    def test_coordinator_without_run_record_requires_actual_metadata(self):
        self.steering()
        self.run_path.unlink()
        self.actor = 'ash'
        self.env.pop('CREW_ID')
        self.refused('steer', '--source', '123', '--command', 'hold')
        r = self.ack('steer', '--source', '123', '--command', 'hold', '--engine', 'claude-code sonnet medium',
                     '--harness', 'claude-code', '--start', '2026-11-13T00:00:00Z')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('— 🔥 Ash (CTO) · claude-code · sonnet', self.effects()[0]['body'])

    def merge(self):
        previous = {'author': {'login': 'acme-reviewer'}, 'body':
                    '<!-- crew:v1 role=reviewer-validator pass=verdict pr=9 sha=%s base=%s round=1 verdict=changes -->\n'
                    '— 🔎 Vera (Reviewer-validator) · claude-code · sonnet' % (self.head, self.base)}
        self.git('switch', '-q', 'main')
        Path(self.project_dir, 'upstream').write_text('new\n')
        self.git('add', 'upstream')
        self.git('commit', '-q', '-m', 'upstream')
        updated = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/remotes/origin/main', updated)
        self.git('switch', '-q', 'builder/7-test')
        self.git('merge', '-q', '--no-ff', 'main', '-m', 'merge')
        verified = self.head
        self.head = self.git('rev-parse', 'HEAD')
        self.rec.update(head=self.head, args={'pr': 9, 'round': 2})
        self.data['pr'].update(headRefOid=self.head, reviews=[previous])
        self.save()
        return ('--verified-base', self.base, '--verified-head', verified, '--updated-base', updated)

    def test_clean_merge_after_changes_keeps_findings_and_deduplicates(self):
        refs = self.merge()
        r = self.ack('merge-up', *refs)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('unresolved findings remain', self.effects()[0]['body'])
        self.assertEqual(self.ack('merge-up', *refs).returncode, 0)
        self.assertEqual(len(self.effects()), 1)

    def test_merge_up_wrong_parent_order_refuses_identical_content(self):
        refs = self.merge()
        tree = self.git('rev-parse', 'HEAD^{tree}')
        self.head = self.git('commit-tree', tree, '-p', refs[5], '-p', refs[3], '-m', 'reversed parents')
        self.git('update-ref', 'HEAD', self.head)
        self.rec['head'] = self.head
        self.data['pr']['headRefOid'] = self.head
        self.save()
        r = self.ack('merge-up', *refs)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('unverified merge parents', r.stdout)
        self.assertEqual(self.effects(), [])

    def test_merge_up_missing_pass_verdict_and_changed_content_refuse(self):
        refs = self.merge()
        previous = self.data['pr']['reviews'][0]['body']
        for invalid in (previous.replace('verdict=changes', 'verdict=pass'), previous.replace('pr=9', 'pr=10')):
            self.data['pr']['reviews'][0]['body'] = invalid
            self.save()
            self.refused('merge-up', *refs)
        self.data['pr']['reviews'][0]['body'] = previous
        Path(self.project_dir, 'feature').write_text('rewritten\n')
        self.git('add', 'feature')
        self.git('commit', '-q', '--amend', '--no-edit')
        self.head = self.git('rev-parse', 'HEAD')
        self.rec['head'] = self.head
        self.data['pr']['headRefOid'] = self.head
        self.save()
        self.refused('merge-up', *refs)

    def steering(self):
        self.rec['role'] = 'coordinator'
        self.rec['pass'] = 'coordinate'
        self.env['CREW_ROLE'] = 'coordinator'
        self.data['login'] = 'acme-bot'
        self.data['source'] = {'id': 123, 'user': {'login': 'acme-owner'}, 'body': '/crew hold',
                               'issue_url': 'https://api.github.com/repos/acme/widgets/issues/9',
                               'created_at': '2026-11-13T00:00:00Z', 'updated_at': '2026-11-13T00:00:00Z'}
        self.save()
        return ('--source', '123', '--command', 'hold')

    def test_owner_steer_deduplicates_without_executing(self):
        flags = self.steering()
        self.rec['pass'] = 'review'
        self.save()
        self.refused('steer', *flags)
        self.rec['pass'] = 'coordinate'
        self.save()
        r = self.ack('steer', *flags)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('cmd=hold cmd-id=123', self.effects()[0]['body'])
        self.assertEqual(self.ack('steer', *flags).returncode, 0)
        self.assertEqual(len(self.effects()), 1)
        self.assertEqual(json.loads(self.data_path.read_text())['pr']['labels'], [])

    def test_steer_wrong_edited_foreign_and_authorization_sources_refuse(self):
        flags = self.steering()
        for patch in ({'user': {'login': 'acme-bot'}}, {'updated_at': 'later'},
                      {'issue_url': 'https://api.github.com/repos/acme/widgets/issues/10'}, {'body': 'please hold'}):
            with self.subTest(patch=patch):
                old = dict(self.data['source'])
                self.data['source'].update(patch)
                self.save()
                self.refused('steer', *flags)
                self.data['source'] = old
        self.save()
        for cmd in ('merge-ok', 'resume', 'cutover', 'plan-ok', 'rereview', 'away', 'away-return', 'rework',
                    'urgent', 'stop-landing', 'resume-landing', 'hold-release'):
            with self.subTest(command=cmd):
                self.data['source']['body'] = '/crew ' + cmd
                self.save()
                self.refused('steer', '--source', '123', '--command', cmd)
        self.refused('steer', '--source', '123', '--command', 'unknown')

    def test_steer_hold_exception_does_not_clear_hold(self):
        self.steering()
        self.data['pr']['labels'] = [{'name': 'crew:hold'}]
        self.save()
        self.refused('steer', '--source', '123', '--command', 'hold')
        self.data['source']['body'] = '/crew escalate'
        self.save()
        r = self.ack('steer', '--source', '123', '--command', 'escalate')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(json.loads(self.data_path.read_text())['pr']['labels'], [{'name': 'crew:hold'}])


if __name__ == '__main__':
    unittest.main()
