"""Validate version evidence and render the same section on every purifier page."""
from html import escape
import re

ROLES = {
    'native-tool': 'Build tool / package manager',
    'native-tool-runtime': 'Runtime running the tool',
    'project-runtime': 'Project runtime',
    'compiler': 'Project compiler',
    'host-helper': 'Capture / build helper',
    'addon-target': 'Native addon target',
    'build-target': 'Build target',
    'native-format': 'Native lock / package format',
}
OPERATIONS = {
    'pure-build': 'Nix build', 'native-lock': 'Native lock capture',
    'native-prefetch': 'Prefetch', 'native-install-offline': 'Offline native install',
    'project-build-scripts': 'Project build', 'project-test-scripts': 'Project tests',
    'production-install': 'Production dependency install', 'release-pack': 'Release archive',
    'outgoing-capture': 'Outgoing package capture', 'native-publish': 'Native publication',
    'pure-native-byte-equality': 'Matching native/Nix publication bytes',
    'source-preservation': 'Unchanged project sources',
}
EMPTY = {'defaults': [], 'testedPoints': [], 'supportedRanges': [], 'limitations': []}


def validate(data):
    if not isinstance(data, dict) or set(data) != set(EMPTY):
        raise ValueError('compatibility requires defaults, testedPoints, supportedRanges and limitations')
    if any(not isinstance(value, list) for value in data.values()):
        raise ValueError('compatibility fields must be lists')
    def text(value):
        return isinstance(value, str) and bool(value.strip())
    def texts(value):
        return isinstance(value, list) and bool(value) and all(text(x) for x in value)
    def proof(item):
        if not re.fullmatch(r'[a-f0-9]{40}', item.get('sourceRevision', '')) or not texts(item.get('evidence')):
            raise ValueError('version evidence requires an exact source revision and evidence links')
        if any(not re.fullmatch(r'https://[^\s]+', link) for link in item['evidence']):
            raise ValueError('version evidence requires HTTPS links')
    def component(item):
        if item.get('role') not in ROLES or not text(item.get('name')) or not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z.+_:-]*', item.get('version', '')):
            raise ValueError('version components require a known role, name and exact version')
    for item in data['defaults']:
        if set(item) != {'role', 'name', 'version', 'sourceRevision', 'evidence'}:
            raise ValueError('invalid packaged default')
        component(item); proof(item)
    ids = set()
    for point in data['testedPoints']:
        if set(point) != {'id', 'components', 'system', 'operations', 'sourceRevision', 'evidence', 'notes'}:
            raise ValueError('invalid tested version combination')
        proof(point)
        if not text(point['id']) or point['id'] in ids or not text(point['system']) or not texts(point['operations']):
            raise ValueError('tested version combinations need unique IDs, a system and operations')
        if not isinstance(point['notes'], list) or any(not text(x) for x in point['notes']):
            raise ValueError('version notes must be nonempty strings')
        ids.add(point['id']); keys = set()
        if not isinstance(point['components'], list) or not point['components']:
            raise ValueError('tested version combinations require components')
        for item in point['components']:
            if set(item) != {'role', 'name', 'version'}:
                raise ValueError('invalid version component fields')
            component(item); key = item['role'], item['name']
            if key in keys:
                raise ValueError('a tested combination cannot select two versions of the same component')
            keys.add(key)
    for item in data['supportedRanges']:
        if set(item) != {'role', 'name', 'range', 'systems', 'operations', 'basis', 'supportingTests', 'sourceRevision', 'evidence'}:
            raise ValueError('invalid supported version range')
        proof(item)
        if (item['role'] not in ROLES or not all(text(item[x]) for x in ('name', 'range', 'basis'))
                or not all(texts(item[x]) for x in ('systems', 'operations', 'supportingTests'))
                or not set(item['supportingTests']) <= ids):
            raise ValueError('supported ranges require explicit review and existing supporting tests')
    for item in data['limitations']:
        if set(item) != {'text', 'sourceRevision', 'evidence'} or not text(item['text']):
            raise ValueError('invalid version limitation')
        proof(item)
    return data


def cell(value):
    return escape(str(value)).replace('|', '&#124;').replace('\n', ' ')


def evidence(item):
    return ' · '.join('[CI run](' + url + ')' if '/actions/runs/' in url else
                      '[Test fixture](' + url + ')' for url in item['evidence'])


def render_compatibility(page, contract, heading=True):
    spec = contract['versionCompatibility']
    data = validate(page.get('compatibility', EMPTY))
    lines = ['## ' + spec['title']] if heading else []
    if not any(data.values()):
        lines.append(spec['unknown'])
        return '\n\n'.join(lines)
    lines += [spec['introduction']]
    if data['defaults']:
        lines += ['### Packaged defaults', '| Component | Version |', '|---|---|']
        lines += [f'| {ROLES[x["role"]]}: {cell(x["name"])} | {cell(x["version"])} |' for x in data['defaults']]
    if data['supportedRanges']:
        lines += ['### Supported ranges']
        for item in data['supportedRanges']:
            lines.append(f'{ROLES[item["role"]]} **{cell(item["name"])}**: {cell(item["range"])} '
                         f'({cell(", ".join(item["systems"]))}; {cell(", ".join(item["operations"]))}). '
                         + cell(item['basis']) + ' ' + evidence(item))
    else:
        lines.append(spec['noRanges'])
    if data['testedPoints']:
        lines += ['### Tested combinations', spec['pointScope'],
                  '| Versions and roles | Platform | Checked operations | Evidence |', '|---|---|---|---|']
        for point in data['testedPoints']:
            components = '<br>'.join(f'{ROLES[c["role"]]}: {cell(c["name"])} {cell(c["version"])}' for c in point['components'])
            operations = ', '.join(cell(OPERATIONS.get(op, op.replace('-', ' '))) for op in point['operations'])
            if point['notes']:
                operations += '<br>' + ' '.join(cell(note) for note in point['notes'])
            lines.append(f'| {components} | {cell(point["system"])} | {operations} | {evidence(point)} |')
    else:
        lines.append(spec['noTests'])
    if data['limitations']:
        lines += ['### Version limitations']
        lines += ['- ' + cell(item['text']) + ' ' + evidence(item) for item in data['limitations']]
    return '\n\n'.join(_tables(lines))


def _tables(lines):
    """Keep Markdown table rows contiguous and paragraphs separated."""
    result = []
    for line in lines:
        if result and line.startswith('|') and result[-1].startswith('|'):
            result[-1] += '\n' + line
        else:
            result.append(line)
    return result
