"""Evidence-backed quality assessments, independent of version compatibility."""
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

CRITERIA = ('evaluation', 'goodTests', 'linux', 'darwin', 'oneVersion',
            'nonEolVersions', 'manySamples', 'longCompatibility')
LABELS = dict(zip(CRITERIA, ('Nix evaluation', 'Test quality', 'Linux builds', 'Darwin builds',
                           'Supported version', 'Non-EOL coverage', 'Sample breadth', 'Historical compatibility')))
DEFINITIONS = {int(tier): description for tier, description in json.loads(
    (Path(__file__).resolve().parents[1] / 'model/tiers.json').read_text())['definitions'].items()}


def registry():
    data = json.loads((Path(__file__).resolve().parents[1] / 'model/tiers.json').read_text())
    if data.get('version') != 1 or not isinstance(data.get('projects'), dict):
        raise ValueError('expected version 1 quality-tier registry')
    for name, assessment in data['projects'].items():
        if not re.fullmatch(r'[a-z0-9-]+-purifier', name):
            raise ValueError('invalid quality assessment project name')
        validate(assessment)
    return data


def validate(q):
    if not isinstance(q, dict) or set(q) != {'tier', 'reviewedRevision', 'reviewedAt', 'rationale', 'criteria', 'sampleBuilds'}:
        raise ValueError('quality assessment has missing or unknown fields')
    if type(q['tier']) is not int or q['tier'] not in DEFINITIONS:
        raise ValueError('quality tier must be 1 through 4')
    if not re.fullmatch(r'[a-f0-9]{40}', q['reviewedRevision']) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', q['reviewedAt']):
        raise ValueError('quality assessment needs an exact revision and review date')
    if not isinstance(q['rationale'], str) or not q['rationale'].strip():
        raise ValueError('quality assessment requires a rationale')
    if not isinstance(q['criteria'], dict) or set(q['criteria']) != set(CRITERIA):
        raise ValueError('quality assessment must review every tier criterion')
    def evidence(value):
        return isinstance(value, list) and all(isinstance(s, str) and re.fullmatch(r'https://[^\s]+', s) for s in value)
    for criterion in q['criteria'].values():
        if set(criterion) != {'state', 'summary', 'evidence'} or criterion['state'] not in {'met', 'not-met', 'unreviewed'}:
            raise ValueError('invalid tier criterion')
        if not isinstance(criterion['summary'], str) or not criterion['summary'].strip() or not evidence(criterion['evidence']):
            raise ValueError('tier criteria need a summary and valid evidence links')
        if criterion['state'] == 'met' and not criterion['evidence']:
            raise ValueError('met tier criteria require evidence')
    if not isinstance(q['sampleBuilds'], list):
        raise ValueError('sample builds must be a list')
    names = []
    for sample in q['sampleBuilds']:
        if set(sample) != {'name', 'evidence'} or not isinstance(sample['name'], str) or not sample['name'].strip() or not evidence(sample['evidence']) or not sample['evidence']:
            raise ValueError('confirmed sample builds require identity and evidence')
        names.append(sample['name'])
    if len(names) != len(set(names)):
        raise ValueError('duplicate sample builds do not establish breadth')
    met = lambda key: q['criteria'][key]['state'] == 'met'
    if not met('evaluation'):
        raise ValueError('even Tier 4 requires evaluation evidence')
    third = bool(names) and met('linux') and met('oneVersion')
    second = third and met('goodTests') and met('darwin') and met('nonEolVersions')
    first = third and met('goodTests') and met('darwin') and met('manySamples') and met('longCompatibility')
    best = 1 if first else 2 if second else 3 if third else 4
    if q['tier'] != best:
        raise ValueError('tier does not match its evidenced criteria')
    return q


def for_repository(repository, data=None):
    data = registry() if data is None else data
    owner, _, name = repository.partition('/')
    return data['projects'].get(name) if owner == 'nix-purifiers' else None


def evidence_label(url):
    path = urlsplit(url).path
    if '/actions/runs/' in path:
        return 'Native CI job' if '/job/' in path else 'Native CI run'
    if path.endswith('/.github/workflows/check.yml'):
        return 'Native CI workflow'
    if path.endswith('/tests/default.nix') or path.endswith('/flake.nix'):
        return 'Sample build definitions'
    if '/tree/' in path:
        return 'Checked-in sample sources'
    if 'go.dev' in url:
        return 'Upstream Go support policy'
    return Path(path).name or urlsplit(url).hostname


def render_tiers(data):
    modeled = json.loads((Path(__file__).parent / 'catalog.json').read_text())['catalog']
    lines = ['# Purifier tiers',
             'Tiers describe reviewed test and compatibility coverage. Lower numbers have broader evidence; they do not replace the exact version and platform notes.',
             '| Tier | Requirements |', '| --- | --- |']
    lines += [f'| {tier} | {description} |' for tier, description in DEFINITIONS.items()]
    lines += ['', '“Good tests,” “many samples,” and “a long way” are reviewed judgments with linked evidence, not numerical cutoffs. An unreviewed required criterion prevents promotion; it does not mean a tool is known to fail. Declared systems and Darwin evaluation alone do not prove Darwin works.',
              'Assessments are revision-bound. Non-EOL coverage needs an upstream support-policy review; historical version points alone do not establish it. Local drafts and native experiments are not published purifiers.',
              'The registry covers published purifiers, including projects not yet in the structured behavior catalog. [Machine-readable assessments](quality.json).']
    for tier in DEFINITIONS:
        group = [(name, q) for name, q in sorted(data['projects'].items()) if q['tier'] == tier]
        lines += [f'## Tier {tier}', f'{len(group)} purifiers.']
        for name, q in group:
            documentation = f'[Documentation](https://nix-purifiers.github.io/{name}/)' if name in modeled else f'[Project source](https://github.com/nix-purifiers/{name})'
            lines += [f'### {name}', f'{documentation} · reviewed {q["reviewedAt"]} · [source revision](https://github.com/nix-purifiers/{name}/tree/{q["reviewedRevision"]})', q['rationale'],
                      '<details markdown="1"><summary>Criteria and evidence</summary>',
                      '| Criterion | State | Review |', '| --- | --- | --- |']
            for key, item in q['criteria'].items():
                state = {'met': 'Met', 'not-met': 'Not met', 'unreviewed': 'Unreviewed'}[item['state']]
                lines.append(f'| {LABELS[key]} | {state} | {escape(item["summary"])} |')
            sources = dict.fromkeys(url for item in q['criteria'].values() for url in item['evidence'])
            lines.append('Evidence: ' + ', '.join(f'[{evidence_label(url)}]({url})' for url in sources) + '.')
            if q['sampleBuilds']:
                lines.append('Confirmed sample builds: ' + '; '.join(f'[{escape(s["name"])}]({s["evidence"][0]})' for s in q['sampleBuilds']) + '.')
            lines.append('</details>')
    return re.sub(r'(?<=\|)\n\n(?=\|)', '\n', '\n\n'.join(lines)) + '\n'


def homepage(text, data):
    text = re.sub(r' <a class="tier-badge"[^>]*>Tier [1-4]</a>', '', text)
    for name, q in data['projects'].items():
        text = text.replace(f'>{name}</a>', f'>{name}</a> <a class="tier-badge" href="/tiers.html#{name}">Tier {q["tier"]}</a>')
    return text
