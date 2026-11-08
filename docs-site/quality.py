"""Evidence-backed quality assessments, independent of version compatibility."""
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from derivation_evidence import validate_review, render_receipts
from receipt_artifacts import verify_local
from native_ci_evidence import read_native_artifact
from quality_policy import TECHNICAL_CRITERIA, HUMAN_CRITERIA, LABELS, criterion_keys, best_tier, require_current_registry
from human_use_evidence import validate_review as validate_human_review, render_reports

RECEIPT_BASE = "https://nix-purifiers.github.io/evidence/"
RECEIPT_DIRECTORY = Path(__file__).parent / "evidence"

REGISTRY_VERSION = 3
CRITERIA = criterion_keys(REGISTRY_VERSION)
DEFINITIONS = {int(tier): description for tier, description in json.loads(
    (Path(__file__).resolve().parents[1] / 'model/tiers.json').read_text())['definitions'].items()}


def registry():
    data = json.loads((Path(__file__).resolve().parents[1] / 'model/tiers.json').read_text())
    require_current_registry(data.get('version'))
    if not isinstance(data.get('projects'), dict):
        raise ValueError('expected completed quality-tier registry')
    for name, assessment in data['projects'].items():
        if not re.fullmatch(r'[a-z0-9-]+-purifier', name):
            raise ValueError('invalid quality assessment project name')
        validate(assessment, "nix-purifiers/" + name)
    artifacts = json.loads((Path(__file__).resolve().parents[1] / "model/review-artifacts.json").read_text())
    for group in artifacts.values():
        for reference in group.values():
            if 'format' in reference:
                read_native_artifact(RECEIPT_DIRECTORY, RECEIPT_BASE, reference)
            else:
                verify_local(RECEIPT_DIRECTORY, RECEIPT_BASE, reference)
    return data


def validate(q, repository=None):
    version = 3
    criteria = criterion_keys(version)
    fields = {'tier', 'reviewedRevision', 'reviewedAt', 'rationale', 'criteria', 'sampleBuilds', 'derivationReview'}
    if version == 3:
        fields.add('humanUseReview')
    if not isinstance(q, dict) or set(q) != fields:
        raise ValueError('quality assessment has missing or unknown fields')
    if type(q['tier']) is not int or q['tier'] not in DEFINITIONS:
        raise ValueError('quality tier must be 1 through 4')
    if not re.fullmatch(r'[a-f0-9]{40}', q['reviewedRevision']) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', q['reviewedAt']):
        raise ValueError('quality assessment needs an exact revision and review date')
    if not isinstance(q['rationale'], str) or not q['rationale'].strip():
        raise ValueError('quality assessment requires a rationale')
    if not isinstance(q['criteria'], dict) or set(q['criteria']) != set(criteria):
        raise ValueError('quality assessment must review every tier criterion')
    def evidence(value):
        return isinstance(value, list) and all(isinstance(s, str) and re.fullmatch(r'https://[^\s]+', s) for s in value)
    for criterion in q['criteria'].values():
        if set(criterion) != {'state', 'summary', 'evidence'} or criterion['state'] not in {'met', 'not-met'}:
            raise ValueError('invalid tier criterion')
        if not isinstance(criterion['summary'], str) or not criterion['summary'].strip() or not evidence(criterion['evidence']):
            raise ValueError('tier criteria need a summary and valid evidence links')
    review = q['derivationReview']
    if repository is None:
        repositories = {e['repository'] for e in review['derivations'].values()}
        if len(repositories) != 1:
            raise ValueError('quality review needs one repository identity')
        repository = repositories.pop()
    validate_review(repository, q['reviewedRevision'], review, RECEIPT_DIRECTORY, RECEIPT_BASE)
    for key in TECHNICAL_CRITERIA:
        if any(q['criteria'][key][field] != review['criteria'][key][field]
               for field in ('state', 'summary')):
            raise ValueError('completed review differs from assessment judgment')
    if version == 3:
        validate_human_review(repository, q['humanUseReview'])
        for key in HUMAN_CRITERIA:
            if any(q['criteria'][key][field] != q['humanUseReview']['criteria'][key][field]
                   for field in ('state', 'summary')):
                raise ValueError('human use review differs from assessment judgment')
    if [s['name'] for s in q['sampleBuilds']] != [s['name'] for s in review['sampleBuilds']]:
        raise ValueError('completed review differs from assessment samples')
    for e in review['derivations'].values():
        if e.get('kind') == 'native-ci-execution':
            continue  # Native validator verifies both exact retained job/log artifacts.
        for receipt in (e['evaluation'], e['build']):
            if receipt is not None:
                verify_local(RECEIPT_DIRECTORY, RECEIPT_BASE, receipt)
        replay = e['check']['replay']
        if replay is not None:
            verify_local(RECEIPT_DIRECTORY, RECEIPT_BASE,
                         {'receipt': replay['artifactUrl'], 'artifactSha256': replay['artifactSha256']})
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
    best = best_tier(version, q['criteria'], bool(names))
    if q['tier'] != best:
        raise ValueError('tier does not match its evidenced criteria')
    return q


def for_repository(repository, data=None):
    data = registry() if data is None else data
    require_current_registry(data.get('version'))
    owner, _, name = repository.partition('/')
    return data['projects'].get(name) if owner == 'nix-purifiers' else None


def evidence_label(url):
    path = urlsplit(url).path
    if '/actions/runs/' in path:
        return 'Native CI job' if '/job/' in path else 'Native CI run'
    if '/evidence/' in path and re.fullmatch(r'[0-9a-f]{64}\.(json|log)', Path(path).name):
        return 'Retained review artifact'
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
    require_current_registry(data.get('version'))
    modeled = json.loads((Path(__file__).parent / 'catalog.json').read_text())['catalog']
    criteria = criterion_keys(data['version'])
    definitions = {int(tier): value for tier, value in data['definitions'].items()}
    introduction = ('Tiers describe reviewed human use, tests and compatibility. Lower numbers require broader evidence; exact use, version and platform scopes remain explicit.'
                    if data['version'] == 3 else
                    'Tiers describe reviewed test and compatibility coverage. Lower numbers have broader evidence; they do not replace the exact version and platform notes.')
    lines = ['# Purifier tiers', introduction,
             '| Tier | Requirements |', '| --- | --- |']
    lines += [f'| {tier} | {description} |' for tier, description in definitions.items()]
    lines += ['', '“Good tests,” “many samples,” and “a long way” are reviewed judgments with linked evidence, not numerical cutoffs. Every criterion has a completed review. Not met means the inspected evidence does not demonstrate the criterion; it does not mean a tool is known to fail. Declared systems and Darwin evaluation alone do not prove Darwin works.',
              ('Technical assessments are revision-bound; human reports retain their own dates and stated use scope. ' if data['version'] == 3 else 'Assessments are revision-bound. ') + 'Non-EOL coverage needs an upstream support-policy review; historical version points alone do not establish it. Local drafts and native experiments are not published purifiers.',
              'The registry covers published purifiers, including projects not yet in the structured behavior catalog. [Machine-readable assessments](quality.json).']
    if data['version'] == 3:
        lines += ['A clear human firsthand report can include maintainer or contributor sample-project use. Ongoing real usage is a separate reviewed judgment; neither criterion is inferred from CI or authorship. Direct attestations may be private, with only reviewed scope disclosed.']
    for tier in definitions:
        group = [(name, q) for name, q in sorted(data['projects'].items()) if q['tier'] == tier]
        if not group:
            continue
        lines += [f'## Tier {tier}', f'{len(group)} purifiers.']
        for name, q in group:
            documentation = f'[Documentation](https://nix-purifiers.github.io/{name}/)' if name in modeled else f'[Project source](https://github.com/nix-purifiers/{name})'
            lines += [f'### {name}', f'{documentation} · reviewed {q["reviewedAt"]} · [source revision](https://github.com/nix-purifiers/{name}/tree/{q["reviewedRevision"]})', q['rationale'],
                      '<details markdown="1"><summary>Criteria and evidence</summary>',
                      '| Criterion | State | Review |', '| --- | --- | --- |']
            for key in criteria:
                item = q['criteria'][key]
                state = {'met': 'Met', 'not-met': 'Not met'}[item['state']]
                summary = escape(item['summary']).replace('|', '&#124;').replace('\n', ' ')
                lines.append(f'| {LABELS[key]} | {state} | {summary} |')
            sources = dict.fromkeys(url for key in TECHNICAL_CRITERIA for url in q['criteria'][key]['evidence'])
            lines.append('Review references (definitions and maintenance policies): ' + ', '.join(f'[{evidence_label(url)}]({url})' for url in sources) + '.')
            if q['sampleBuilds']:
                lines.append('Confirmed sample builds: ' + '; '.join(f'[{escape(s["name"])}]({s["evidence"][0]})' for s in q['sampleBuilds']) + '.')
            for gap in data.get('normalizationGaps', {}).get(name, []):
                lines.append('Receipt gap: ' + escape(gap))
            if data['version'] == 3:
                lines.append('Human-use evidence review:')
                lines.append(render_reports('nix-purifiers/' + name, q['humanUseReview']))
            lines.append('Executable derivations and execution receipts:')
            lines.append(render_receipts(q['derivationReview']))
            lines.append('</details>')
    return re.sub(r'(?<=\|)\n\n(?=\|)', '\n', '\n\n'.join(lines)) + '\n'


def homepage(text, data):
    start = '<!-- purifier-tier-groups:start -->'
    end = '<!-- purifier-tier-groups:end -->'
    if text.count(start) != text.count(end) or text.count(start) > 1:
        raise ValueError('homepage tier group markers are malformed')
    if start in text and end in text:
        left = text.index(start)
        right = text.index(end, left) + len(end)
    else:
        listing = re.search(r'<ul>.*?</ul>', text, re.DOTALL)
        if listing is None:
            raise ValueError('homepage requires a purifier list')
        left, right = listing.span()
    entries = re.findall(r'<li\b[^>]*>.*?</li>', text[left:right], re.DOTALL)
    groups, seen = {}, set()
    for entry in entries:
        # Remove the previous per-line presentation without touching project
        # links, descriptions, or their order within each tier.
        entry = re.sub(r' <a class="tier-badge"[^>]*>Tier [1-4]</a>', '', entry)
        project = re.search(r'>([a-z0-9-]+-purifier)</a>', entry)
        if project is None or project[1] not in data['projects']:
            raise ValueError('homepage project requires a tier assessment')
        name = project[1]
        if name in seen:
            raise ValueError('duplicate homepage project')
        seen.add(name)
        groups.setdefault(data['projects'][name]['tier'], []).append(entry)
    if not entries:
        raise ValueError('homepage purifier list is empty')
    sections = []
    for tier, members in sorted(groups.items()):
        sections.append(f'  <section class="tier-group" aria-labelledby="tier-{tier}">\n'
                        f'    <h2 id="tier-{tier}">Tier {tier}</h2>\n'
                        '    <ul>\n' + '\n'.join('      ' + entry for entry in members) +
                        '\n    </ul>\n  </section>')
    replacement = start + '\n' + '\n'.join(sections) + '\n  ' + end
    return text[:left] + replacement + text[right:]
