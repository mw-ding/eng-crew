#!/usr/bin/env python3
"""Suggest flavor changes from metrics, without network calls or profile writes.

Usage: flavor-suggest.py --csv FILE --repo OWNER/REPO --flavor NAME --last-change YYYY-MM-DD
       [--as-of YYYY-MM-DD] [--goal quality|speed|cost] [--scope project|CLASS]
       [--feedback FILE] [--defects FILE] [--metrics-gate-open] [--declined FILE] [--knobs FILE]

CSV: metrics-refresh.py columns including flavor, escaped_defects, engine_runs.
Class scopes require a flavor_scope column matching --scope; project excludes
class rows. Feedback is a JSON list of {repo, scope, class, date, link} cards;
class is missed-bug, too-slow or too-costly. Declined is {date, signals: {ID: strength}}
for this project/scope. --knobs is the resolved custom flavor's rigor knobs.
Custom tighten steps review, validation, evidence and precheck; R1/speed R3
relax steps review and validation; R2/cost R3 relax steps caps and precheck.
Other custom knobs stay unchanged. Presets move on thorough <-> standard <-> fast;
solo moves on the standard ladder while preserving builder=solo.
Only merged changes under the current flavor count. Defect dates are unavailable
in the CSV: escaped defects on changes merged in 30 days are the T1/R guards'
proxy for tightening only. --defects is a complete JSON list of {repo, scope,
date, link} discovery records; required to verify the 30-day no-defect relax
guard, including defects discovered on older changes. An empty list verifies zero.
Prints a suggestion body for the coordinator, or NONE. Exit 0: report, 2: input
error. A proposal is unvalidated until crew-config.py validate succeeds; never
apply automatically. Protocol: docs/flavors.md, feedback loop.
"""
import argparse
import csv
import json
import math
import statistics
import sys
from datetime import date, datetime, timedelta, timezone

ORDER = {
    'review': ['full', 'thin', 'light'],
    'validation': ['always', 'behaviour', 'off'],
    'diversity': ['required', 'waivable'],
    'caps': [[3, 3], [2, 2], [1, 1]],
    'evidence': ['typed', 'inline'],
    'merge': ['per-change', 'docs', 'auto'],
    'precheck': ['on', 'off'],
    'lighter_lane': ['off', 'docs', 'docs+tests'],
}
PRESETS = {
    'thorough': ['full', 'always', 'waivable', [3, 3], 'typed', 'docs', 'on', 'docs'],
    'standard': ['thin', 'behaviour', 'waivable', [3, 3], 'typed', 'docs', 'on', 'docs'],
    'fast': ['thin', 'off', 'waivable', [2, 2], 'inline', 'auto', 'off', 'docs+tests'],
}


def read_json(path, default):
    if not path:
        return default
    with open(path) as f:
        return json.load(f)


def load_rows(path, repo, flavor, scope):
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        required = {'repo', 'pr', 'merged_at', 'flavor', 'changes_verdicts',
                    'reopened', 'escaped_defects', 'engine_runs', 'open_to_merge_min'}
        missing = required - set(reader.fieldnames or [])
        if scope != 'project' and 'flavor_scope' not in (reader.fieldnames or []):
            missing.add('flavor_scope')
        if missing:
            raise ValueError('missing CSV columns: ' + ', '.join(sorted(missing)))
        rows = []
        for r in reader:
            if (r['repo'] != repo or r['flavor'] != flavor or not r['merged_at']
                    or (r.get('flavor_scope') or 'project') != scope):
                continue
            r['day'] = datetime.strptime(r['merged_at'], '%Y-%m-%dT%H:%M:%SZ').date()
            for key in ('changes_verdicts', 'escaped_defects', 'engine_runs', 'open_to_merge_min'):
                r[key] = float(r[key])
                if not math.isfinite(r[key]) or r[key] < 0:
                    raise ValueError('invalid metric: ' + key)
            rows.append(r)
        return sorted(rows, key=lambda r: (r['merged_at'], int(r['pr'])))


def signals(rows, cards, cfg):
    end = cfg.as_of + timedelta(days=1)
    rows = [r for r in rows if cfg.last_change <= r['day'] < end]
    recent = [r for r in rows if end - timedelta(days=30) <= r['day']]
    last = rows[-20:]
    escaped = sum(r['escaped_defects'] for r in recent)
    if cfg.defects:
        escaped = sum(d['repo'] == cfg.repo and d.get('scope', 'project') == cfg.scope
                      and end - timedelta(days=30) <= date.fromisoformat(d['date']) < end
                      for d in read_json(cfg.defects, []))
    cards = [c for c in cards if c['repo'] == cfg.repo
             and c.get('scope', 'project') == cfg.scope
             and cfg.last_change <= date.fromisoformat(c['date']) < end]
    tighten, relax = {}, {}
    if escaped >= 2:
        tighten['T1'] = escaped
    missed = sum(c['class'] == 'missed-bug' for c in cards)
    if missed:
        tighten['T2'] = missed
    preset = 'standard' if cfg.flavor == 'solo' else cfg.flavor
    caps = PRESETS[preset][3] if preset in PRESETS else read_json(cfg.knobs, {}).get('caps')
    if not isinstance(caps, list) or len(caps) != 2 or any(type(v) is not int or not 1 <= v <= 3 for v in caps):
        raise ValueError('custom flavor requires resolved caps in --knobs')
    rate = sum(r['reopened'] == 'reopened' or r['changes_verdicts'] >= caps[0] for r in last) / len(last) if last else 0
    if len(last) >= 5 and rate > .2:
        tighten['T3'] = rate
    if len(last) == 20 and not any(r['changes_verdicts'] or r['escaped_defects'] for r in last):
        relax['R1'] = 20
    feedback = [c for c in cards if c['class'] in ('too-slow', 'too-costly')
                and date.fromisoformat(c['date']) >= end - timedelta(days=30)]
    if feedback and not escaped:
        relax['R2'] = len(feedback)
    if cfg.goal != 'quality' and not escaped:
        cur = [r for r in rows if end - timedelta(days=14) <= r['day']]
        base = [r for r in rows if end - timedelta(days=28) <= r['day'] < end - timedelta(days=14)]
        if len(cur) >= 3 and len(base) >= 3:
            key = 'open_to_merge_min' if cfg.goal == 'speed' else 'engine_runs'
            metric = lambda rs: statistics.median(r[key] for r in rs) if cfg.goal == 'speed' else sum(r[key] for r in rs) / len(rs)
            baseline = metric(base)
            if baseline > 0 and metric(cur) > baseline * 1.3:
                relax['R3'] = metric(cur) / baseline - 1
    if tighten:
        return 'tighten', tighten, rows, cards
    if not cfg.defects or cfg.metrics_gate_open or (cfg.as_of - cfg.last_change).days < 28:
        relax = {}
    return 'relax', relax, rows, cards


def proposal(cfg, direction, fired):
    preset = 'standard' if cfg.flavor == 'solo' else cfg.flavor
    if preset in PRESETS:
        names = list(PRESETS)
        index = names.index(preset) + (-1 if direction == 'tighten' else 1)
        if not 0 <= index < len(names):
            return None
        target = names[index]
        old, new = dict(zip(ORDER, PRESETS[preset])), dict(zip(ORDER, PRESETS[target]))
        if cfg.flavor == 'solo':
            return ('solo-' + direction, old, new, target)
        return target, old, new, None
    old = read_json(cfg.knobs, {})
    if (set(old) != set(ORDER) or any(old[k] not in ORDER[k] for k in ORDER if k != 'caps')
            or not isinstance(old.get('caps'), list) or len(old['caps']) != 2
            or any(type(v) is not int or not 1 <= v <= 3 for v in old['caps'])):
        raise ValueError('custom flavor requires all eight resolved rigor knobs in --knobs')
    new = old.copy()
    keys = {'review', 'validation', 'evidence', 'precheck'} if direction == 'tighten' else {'review', 'validation'}
    if direction == 'relax' and ('R2' in fired or (cfg.goal == 'cost' and 'R3' in fired)):
        keys = {'caps', 'precheck'}
    for key in keys:
        if key == 'caps':
            step = -1 if direction == 'relax' else 1
            new[key] = [min(3, max(1, v + step)) for v in old[key]]
            continue
        index = ORDER[key].index(old[key]) + (-1 if direction == 'tighten' else 1)
        if 0 <= index < len(ORDER[key]):
            new[key] = ORDER[key][index]
    if new == old:
        return None
    return cfg.flavor, old, new, ''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--csv', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--flavor', required=True)
    parser.add_argument('--last-change', required=True, type=date.fromisoformat)
    parser.add_argument('--as-of', type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument('--goal', choices=['quality', 'speed', 'cost'], default='quality')
    parser.add_argument('--scope', default='project')
    parser.add_argument('--feedback')
    parser.add_argument('--defects')
    parser.add_argument('--metrics-gate-open', action='store_true')
    parser.add_argument('--declined')
    parser.add_argument('--knobs')
    cfg = parser.parse_args(argv)
    try:
        if cfg.last_change > cfg.as_of:
            raise ValueError('last-change is after as-of')
        direction, fired, rows, cards = signals(load_rows(cfg.csv, cfg.repo, cfg.flavor, cfg.scope), read_json(cfg.feedback, []), cfg)
        declined = read_json(cfg.declined, {})
        if declined and 0 <= (cfg.as_of - date.fromisoformat(declined['date'])).days < 28:
            fired = {k: v for k, v in fired.items() if v > declined['signals'].get(k, -1)}
        change = proposal(cfg, direction, fired) if fired else None
        if not change:
            print('NONE: no eligible flavor suggestion; keep ' + cfg.flavor)
            return 0
        target, old, new, base = change
        print(f'Title: flavor: {direction} {cfg.repo} {cfg.flavor} → {target} ({cfg.as_of})')
        print('Label: flavor-suggestion\n\n## Signal\n')
        print(f'{", ".join(fired)} as of {cfg.as_of} (UTC). Scope: {cfg.scope}. Goal: {cfg.goal}.')
        print('Signal strengths: ' + json.dumps(fired, sort_keys=True))
        print('\n## Evidence\n\n| Change | Flavor | Changes verdicts | Escaped defects | Cycle time (min) | Engine runs |\n|---|---|---|---|---|---|')
        for r in rows:
            print(f"| {cfg.repo}#{r['pr']} | {r['flavor']} | {r['changes_verdicts']:g} | {r['escaped_defects']:g} | {r['open_to_merge_min']:g} | {r['engine_runs']:g} |")
        for c in cards:
            print(f"\nOwner feedback: {c['class']} ({c['date']}): {c['link']}")
        print('\nDefect window: ' + ('dated discovery records' if cfg.defects else 'merge-date proxy; relaxation blocked') + '.\n\n## Proposed change\n')
        for d in read_json(cfg.defects, []):
            if d['repo'] == cfg.repo and d.get('scope', 'project') == cfg.scope:
                print(f"Escaped defect: {d['date']}: {d['link']}")
        print(f'{cfg.flavor} → {target}. Knobs: ' + ', '.join(f'{k} {old[k]} → {new[k]}' for k in ORDER if old[k] != new[k]))
        print('\n```toml')
        if cfg.scope == 'project':
            print('[flavor]\nname = ' + json.dumps(target))
        else:
            print('# Replace the matching existing class record; preserve its paths and reason.')
            print('[[flavor.classes]]\npaths = [' + json.dumps(cfg.scope) + ']\nflavor = ' + json.dumps(target))
            print('reason = "Owner acceptance pending; retain the recorded lowering reason"')
        if base is not None:
            print('[flavor.custom.' + json.dumps(target) + ']')
            if base:
                print('base = ' + json.dumps(base))
            else:
                print('# Update only these knobs in the existing custom table; retain base and other settings.')
            for k, v in new.items():
                if base or v != old[k]:
                    print(k + ' = ' + json.dumps(v))
            if cfg.flavor == 'solo':
                print('builder = "solo"')
        print('```\n\nValidator: pending; coordinator must run crew-config.py validate on the proposed profile.')
        print(f'\n## Decision\n\nOwner: `accept flavor: {target}` or `decline flavor: <reason>`.\nDefault if unanswered: keep {cfg.flavor}. A flavor change is never applied by default.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('flavor-suggest: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
