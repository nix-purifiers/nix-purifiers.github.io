"""Publish maintainer testing notes with explicitly labeled data downloads."""
import hashlib
from html import escape
import json
import re


def label(value):
    return escape(str(value).replace('-', ' ').replace('.', ': ')).replace('|', '&#124;').replace('\n', ' ')


def downloads(links):
    return ('\n<details markdown="1">\n<summary>Machine-readable exports</summary>\n\n' +
            ' · '.join(f'[Download {name} (JSON)]({path})' for name, path in links) +
            '\n\n</details>\n')


def project_notes(name, project, contexts):
    text = ('---\nlayout: default\ntitle: ' + json.dumps(name + ' testing notes') + '\n---\n\n'
            f'# {name} testing notes\n\n'
            '[All maintainer testing notes](../) · '
            f'[Project documentation](../../{name}/)\n\n'
            'These notes describe planned checks and any attached execution observations. '
            'Use the project documentation for supported behavior.\n\n')
    if not contexts:
        text += 'No execution evidence is attached to this build. Planned checks do not establish a test result.\n\n'
    text += '## Planned checks\n\n| Check | Applicability | Notes |\n|---|---|---|\n'
    for case in project['obligations']:
        text += f'| {label(case["id"])} | {label(case["applicability"])} | {label(case.get("reason", ""))} |\n'
    for number, context in enumerate(contexts, 1):
        text += f'\n## Recorded context {number}\n\n'
        def fields(value, prefix=''):
            for key, item in value.items():
                if key == 'obligations':
                    continue
                title = prefix + label(key)
                if isinstance(item, dict):
                    yield from fields(item, title + ' / ')
                else:
                    yield title, label(', '.join(map(str, item)) if isinstance(item, list) else item)
        details = list(fields(context))
        if details:
            text += '| Context | Value |\n|---|---|\n' + ''.join(f'| {key} | {value} |\n' for key, value in details) + '\n'
        text += '| Check | Observation | Result |\n|---|---|---|\n'
        for case, observations in context['obligations'].items():
            for observation, result in observations.items():
                text += f'| {label(case)} | {label(observation)} | {label(result)} |\n'
    return text + downloads([('project data', name + '.json')])


def build_testing(plan, evidence, destination):
    encoded = json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if evidence is not None and evidence.get('planDigest') != hashlib.sha256(encoded).hexdigest():
        raise ValueError('Coverage evidence is stale for this plan')
    if evidence is not None and set(evidence['projects']) != set(plan['projects']):
        raise ValueError('Coverage evidence must address every planned project')
    rows = []
    pages = {}
    for name, project in sorted(plan['projects'].items()):
        if name in {'.', '..'} or not re.fullmatch(r'[A-Za-z0-9_.-]+', name):
            raise ValueError('Invalid coverage project name')
        contexts = evidence['projects'][name]['contexts'] if evidence is not None else []
        passed = sum(status == 'passed' for context in contexts
                     for observations in context['obligations'].values() for status in observations.values())
        required = sum(case['applicability'] == 'required' for case in project['obligations'])
        review = sum(case['applicability'] == 'needs-review' for case in project['obligations'])
        rows.append(f'| [{name}](projects/{name}.html) | {required} | {review} | {len(contexts)} | {passed} |')
        pages[name] = project_notes(name, project, contexts)
    text = ('---\nlayout: default\ntitle: Maintainer testing notes\n---\n\n'
            '# Maintainer testing notes\n\n'
            'Test planning and recorded observations for maintainers. '
            'For setup and supported features, start with the [purifier documentation](../).\n\n'
            'Results apply to a specific source, system, native SDK and cache profile. '
            'Lifecycle transitions and projection directions are tracked separately.\n\n')
    text += ('No execution evidence is attached to this build. Planned checks do not establish a test result.\n\n' if evidence is None else
             'The attached evidence records partial execution; consult each context for remaining gaps.\n\n')
    if plan.get('formatPolicies', {}).get('maven', {}).get('supportsExactHardVersionRanges'):
        text += ('Maven publications can encode exact hard version ranges. Coverage distinguishes soft requests, '
                 'incompatible hard requests and explicit exclusions that remove the transitive constraint.\n\n')
    text += (f'The plan contains {len(plan["projectionCandidates"])} projection candidates awaiting compatibility review. '
             'Native SDK matrices and buildable applicability remain explicit review items.\n\n'
             'The final column counts individual assertions that passed across the recorded contexts.\n\n'
             '| Project | Required checks | Applicability reviews | Recorded contexts | Assertions passed |\n'
             '|---|---:|---:|---:|---:|\n' + '\n'.join(rows) + '\n')
    text += downloads([('full plan', 'plan.json')] + ([('execution audit', 'audit.json')] if evidence is not None else []))
    target = destination / 'testing'
    (target / 'projects').mkdir(parents=True, exist_ok=True)
    for pattern in ('*.json', '*.md'):
        for previous in (target / 'projects').glob(pattern):
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
        (target / 'projects' / (name + '.md')).write_text(pages[name])
