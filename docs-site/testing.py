"""Publish coverage obligations and context-bound observations separately."""
import hashlib
import json
import re


def build_testing(plan, evidence, destination):
    encoded = json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if evidence is not None and evidence.get('planDigest') != hashlib.sha256(encoded).hexdigest():
        raise ValueError('Coverage evidence is stale for this plan')
    if evidence is not None and set(evidence['projects']) != set(plan['projects']):
        raise ValueError('Coverage evidence must address every planned project')
    rows = []
    for name, project in sorted(plan['projects'].items()):
        if name in {'.', '..'} or not re.fullmatch(r'[A-Za-z0-9_.-]+', name):
            raise ValueError('Invalid coverage project name')
        contexts = evidence['projects'][name]['contexts'] if evidence is not None else []
        passed = sum(status == 'passed' for context in contexts
                     for observations in context['obligations'].values() for status in observations.values())
        required = sum(case['applicability'] == 'required' for case in project['obligations'])
        review = sum(case['applicability'] == 'needs-review' for case in project['obligations'])
        rows.append(f'| [{name}](projects/{name}.json) | {required} | {review} | {len(contexts)} | {passed} |')
    text = ('---\nlayout: default\ntitle: Testing coverage\n---\n\n'
            '# Testing coverage\n\n'
            'Results apply to a specific source, system, native SDK and cache profile. '
            'Lifecycle transitions, projection directions and both adopter sandwiches have separate obligations.\n\n')
    text += ('No execution evidence is attached to this build.\n\n' if evidence is None else
             'The attached evidence records partial execution; consult each context for remaining gaps.\n\n')
    text += (f'The plan contains {len(plan["projectionCandidates"])} projection candidates awaiting compatibility review. '
             'Native SDK matrices and buildable applicability remain explicit review items.\n\n'
             '[Full plan](plan.json)' + (' · [Execution audit](audit.json)' if evidence is not None else '') + '\n\n'
             '| Project | Required obligations | Applicability reviews | Recorded contexts | Passing observations |\n'
             '|---|---:|---:|---:|---:|\n' + '\n'.join(rows) + '\n')
    target = destination / 'testing'
    (target / 'projects').mkdir(parents=True, exist_ok=True)
    for previous in (target / 'projects').glob('*.json'):
        if previous.stem not in plan['projects']:
            previous.unlink()
    (target / 'index.md').write_text(text)
    (target / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    if evidence is None:
        (target / 'audit.json').unlink(missing_ok=True)
    else:
        (target / 'audit.json').write_text(json.dumps(evidence, indent=2) + '\n')
    for name, project in plan['projects'].items():
        exported = {'plan': project, 'execution': evidence['projects'][name] if evidence is not None else None}
        (target / 'projects' / (name + '.json')).write_text(json.dumps(exported, indent=2) + '\n')
