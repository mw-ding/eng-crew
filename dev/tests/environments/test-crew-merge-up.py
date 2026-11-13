"""Process proof for owned mechanical merge-ups (#239): disposable Git origin and fake native COMMENT backend.

Covers refusal/no effect, rollback, configured union/delta routing, published head, push and post reconciliation.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crew_testlib import Base, ROOT_DIR

FAKE = '''#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
a = sys.argv[1:]
p = Path(os.environ['MERGE_FAKE'])
d = json.loads(p.read_text())
if a[:2] == ['pr', 'view']:
    d['reads'] = d.get('reads', 0) + 1
    h = subprocess.check_output(['git', '--git-dir', d['origin'], 'rev-parse', 'refs/heads/builder/7-test'], text=True).strip()
    d['pr']['headRefOid'] = 'f' * 40 if os.environ.get('MOVE_HEAD') and d['reads'] > 1 else h
    p.write_text(json.dumps(d))
    print(json.dumps(d['pr']))
elif a[:2] == ['api', 'user']:
    print(json.dumps({'login': 'acme-bot'}))
elif a[0] == 'api' and '/reviews' in a[1]:
    if os.environ.get('FAIL_POST'):
        sys.exit(1)
    body = Path(next(x[6:] for x in a if x.startswith('body=@'))).read_text()
    d['effects'].append({'argv': a, 'body': body})
    d['pr']['reviews'].append({'author': {'login': 'acme-bot'}, 'body': body})
    p.write_text(json.dumps(d))
    sys.exit(int(os.environ.get('LOSE_RESPONSE', '0')))
else:
    sys.exit(9)
'''


class MergeUp(Base):
    def git(self, *args, cwd=None):
        r = subprocess.run(['git', '-c', 'user.name=test', '-c', 'user.email=test', *args],
                           cwd=cwd or self.project_dir, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def commit(self, path, text):
        Path(self.project_dir, path).write_text(text)
        self.git('add', path)
        self.git('commit', '-q', '-m', path)
        return self.git('rev-parse', 'HEAD')

    def setUp(self):
        super().setUp()
        self.origin = os.path.join(self.tmp, 'origin.git')
        self.git('init', '--bare', '-q', self.origin)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'test')
        self.git('config', 'user.email', 'test')
        # The profile is runtime input, outside tracked product files.
        self.project = os.path.join(self.tmp, 'config.toml')
        Path(self.project).write_text(Path(self.project_dir, 'crew.toml').read_text() + '\ncheckout = "project"\n')
        Path(self.project_dir, 'crew.toml').unlink()
        self.base = self.commit('common', 'base\n')
        self.git('remote', 'add', 'origin', self.origin)
        self.git('push', '-q', 'origin', 'main')
        self.git('switch', '-q', '-c', 'builder/7-test')
        self.head = self.commit('feature', 'feature\n')
        self.git('push', '-q', 'origin', 'HEAD:refs/heads/builder/7-test')
        self.actor = 'ben-7'
        self.rec = dict(index=10, role='builder', item='issue #7', repo=self.project_dir, claim='claim',
                        worktree=self.project_dir, args={'pr': 9}, head=self.head, engine='codex',
                        model='gpt-6.1-sol', effort='medium', harness='codex', start='2026-11-13T00:00:00Z', **{'pass': 'fix'})
        self.run_path = Path(self.state, 'runs', self.actor + '.json')
        self.run_path.parent.mkdir(parents=True)
        self.run_path.write_text(json.dumps(self.rec))
        self.data_path = Path(self.tmp, 'backend.json')
        self.data = dict(origin=self.origin, effects=[], pr=dict(number=9, state='OPEN', isDraft=False,
                         headRefOid=self.head, headRefName='builder/7-test', isCrossRepository=False,
                         baseRefName='main', labels=[], reviews=[], commits=[], body='', statusCheckRollup=[],
                         closingIssuesReferences=[{'number': 7}]))
        self.save()
        self.env.update(CREW_ID=self.actor, CREW_ROLE='builder', MERGE_FAKE=str(self.data_path))
        Path(self.tmp, 'bin', 'gh').write_text(FAKE)

    def save(self):
        self.data_path.write_text(json.dumps(self.data))

    def merge(self, *extra, **env):
        return self.crew('merge-up', '9', '--head', self.head, '--actor', self.actor, '--repo', self.project_dir,
                         '--check', 'git diff --exit-code', '--project', self.project, *extra, **env)

    def advance(self, path='upstream', text='upstream\n'):
        self.git('switch', '-q', 'main')
        self.updated = self.commit(path, text)
        self.git('push', '-q', 'origin', 'main')
        self.git('switch', '-q', 'builder/7-test')

    def effects(self):
        return json.loads(self.data_path.read_text())['effects']

    def remote(self):
        return self.git('rev-parse', 'refs/heads/builder/7-test', cwd=self.origin)

    def refused(self, *extra, **env):
        r = self.merge(*extra, **env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('refusing', r.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.head)
        self.assertEqual(self.remote(), self.head)
        self.assertEqual(self.effects(), [])
        return r

    def test_current_no_push_or_note(self):
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('current', r.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.head)
        self.assertEqual(self.effects(), [])

    def test_retained_issue_builder_uses_live_copy_not_original_launch_head(self):
        self.advance()
        self.rec.update(head=self.base, args={'issue': 7, 'pr': None})
        self.run_path.write_text(json.dumps(self.rec))
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.effects()), 1)

    def test_foreign_issue_builder_refused(self):
        self.rec['args'] = {'issue': 8, 'pr': None}
        self.run_path.write_text(json.dumps(self.rec))
        self.refused()

    def test_clean_merge_publishes_two_parents_and_native_note(self):
        self.advance()
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        head = self.remote()
        self.assertEqual(self.git('show', '-s', '--format=%P', head).split(), [self.head, self.updated])
        effect, = self.effects()
        self.assertIn('commit_id=' + head, effect['argv'])
        self.assertIn('event=COMMENT', effect['argv'])
        for value in (self.base, self.head, self.updated, head, 'content=identical', 'round=n/a verdict=n/a',
                      '— 🛠️ Ben (Builder) · codex · gpt-6.1-sol', 'exit: 0'):
            self.assertIn(value, effect['body'])
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_configured_union_marks_differing_content_for_delta_review(self):
        self.git('switch', '-q', 'main')
        self.commit('.gitattributes', 'common merge=union\n')
        self.git('switch', '-q', 'builder/7-test')
        self.git('merge', '-q', 'main')
        self.head = self.commit('common', 'feature\n')
        self.rec['head'] = self.head
        self.run_path.write_text(json.dumps(self.rec))
        self.git('push', '-q', 'origin', 'HEAD:refs/heads/builder/7-test')
        self.advance('common', 'upstream\n')
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body = self.effects()[0]['body']
        self.assertIn('Configured union paths: common', body)
        self.assertIn('differing patch requires delta review', body)
        # Load through SourceFileLoader because the shipped entry has no extension.
        from importlib.machinery import SourceFileLoader
        spec = importlib.util.spec_from_loader('merge_cli', SourceFileLoader('merge_cli', os.path.join(ROOT_DIR, 'cli', 'mdstack')))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        self.assertTrue(cli.commands()['route'].merge_up_delta(dict(number=9, reviews=self.effects()), self.remote(), 'Ben'))

    def test_conflict_aborts_and_restores_clean_head(self):
        self.head = self.commit('common', 'feature\n')
        self.rec['head'] = self.head
        self.run_path.write_text(json.dumps(self.rec))
        self.git('push', '-q', 'origin', 'HEAD:refs/heads/builder/7-test')
        self.advance('common', 'upstream\n')
        self.refused()
        self.assertEqual(Path(self.project_dir, 'common').read_text(), 'feature\n')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertFalse(Path(self.project_dir, '.git', 'MERGE_HEAD').exists())

    def test_dirty_untracked_work_is_preserved(self):
        self.advance()
        Path(self.project_dir, 'scratch').write_text('keep\n')
        self.refused()
        self.assertEqual(Path(self.project_dir, 'scratch').read_text(), 'keep\n')

    def test_dirty_tracked_work_is_preserved(self):
        self.advance()
        Path(self.project_dir, 'feature').write_text('keep\n')
        self.refused()
        self.assertEqual(Path(self.project_dir, 'feature').read_text(), 'keep\n')

    def test_git_operation_refused(self):
        Path(self.project_dir, '.git', 'CHERRY_PICK_HEAD').write_text(self.base)
        self.refused()
        self.assertTrue(Path(self.project_dir, '.git', 'CHERRY_PICK_HEAD').exists())

    def test_busy_run_refused(self):
        other = dict(self.rec, role='coordinator')
        Path(self.state, 'runs', 'ash.json').write_text(json.dumps(other))
        self.refused()

    def test_foreign_copy_claim_refused_and_kept(self):
        r = self.crew('copy-claim', 'acquire', '--path', self.project_dir, '--run', 'other', '--project', self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.refused()
        r = self.crew('copy-claim', 'show', '--path', self.project_dir, '--project', self.project)
        self.assertIn('other', r.stdout)

    def test_own_copy_claim_is_not_competitor_or_released(self):
        self.advance()
        self.crew('copy-claim', 'acquire', '--path', self.project_dir, '--run', self.actor, '--project', self.project)
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.crew('copy-claim', 'show', '--path', self.project_dir, '--project', self.project)
        self.assertIn(self.actor, r.stdout)

    def test_pr_state_branch_repo_and_holds_refused(self):
        for key, value in (('state', 'CLOSED'), ('headRefName', 'other'), ('baseRefName', 'other'),
                           ('isCrossRepository', True), ('labels', [{'name': 'crew:hold'}]),
                           ('labels', [{'name': 'crew:escalated'}])):
            with self.subTest(key=key, value=value):
                old = self.data['pr'][key]
                self.data['pr'][key] = value
                self.save()
                self.refused()
                self.data['pr'][key] = old

    def test_wrong_actor_role_head_branch_and_repo_refused(self):
        self.refused('--head', 'a' * 40)
        self.refused('--head', self.head[:7])
        self.refused(CREW_ROLE='coordinator')
        self.git('switch', '-q', '-c', 'other')
        self.refused()
        self.git('switch', '-q', 'builder/7-test')
        self.refused('--repo', self.origin)

    def test_pause_and_unavailable_ownership_refuse(self):
        Path(self.state, 'pause.json').write_text('{"since":"now"}')
        self.refused()
        Path(self.state, 'pause.json').unlink()
        path = Path(self.project)
        path.write_text(path.read_text().replace('[repo]', '[repo]\ncontrol_item = 1').replace('[runtime]', '[runtime]\ninstance = "test"'))
        self.refused()

    def test_rebase_strategy_refused(self):
        from crew_testlib import write_pack
        pack = os.path.join(self.tmp, 'pack')
        org = write_pack(pack)
        with open(os.path.join(pack, 'manifest.toml'), 'a') as f:
            f.write('\n[strategy]\nupdate_from_base = "rebase"\nretains_prior_heads = true\n')
        r = self.refused('--org-profile', org)
        self.assertIn('rebase update strategy refused', r.stdout)

    def test_moved_live_head_before_push_rolls_back(self):
        self.advance()
        self.refused(MOVE_HEAD='1')

    def test_failed_check_rolls_back(self):
        self.advance()
        self.refused('--check', 'git diff --exit-code HEAD^ HEAD')

    def test_push_failure_retains_local_head_and_no_note(self):
        self.advance()
        hook = Path(self.origin, 'hooks', 'pre-receive')
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        r = self.merge()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('push unconfirmed', r.stdout)
        self.assertEqual(self.remote(), self.head)
        self.assertNotEqual(self.git('rev-parse', 'HEAD'), self.head)
        self.assertEqual(self.effects(), [])

    def test_note_failure_reports_published_head_without_another_push(self):
        self.advance()
        r = self.merge(FAIL_POST='1')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('published head=' + self.remote(), r.stdout)
        self.assertIn('do not push again', r.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.remote())
        self.assertEqual(self.effects(), [])

    def test_lost_post_response_confirmed_once_by_readback(self):
        self.advance()
        r = self.merge(LOSE_RESPONSE='1')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('confirmed by readback', r.stdout)
        self.assertEqual(len(self.effects()), 1)


if __name__ == '__main__':
    unittest.main()
