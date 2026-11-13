"""Validate version evidence and render the same section on every purifier page."""
from html import escape
from urllib.parse import urlsplit
from pathlib import Path
from derivation_evidence import validate_receipt, native_success
import hashlib
import json
import re

ROLES = {
    'purifier-implementation': 'Purifier implementation',
    'native-tool': 'Build tool / package manager',
    'native-tool-runtime': 'Runtime running the tool',
    'project-runtime': 'Project runtime',
    'compiler': 'Project compiler',
    'host-helper': 'Capture / build helper',
    'publisher-tool': 'Publication tool',
    'publisher-runtime': 'Runtime running publication',
    'publisher-helper': 'Publication helper',
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
    'ordinary-registry-consumer': 'Ordinary registry consumer',
    'ordinary-package-consumer': 'Ordinary package consumer',
    'ordinary-source-consumer': 'Ordinary source consumer',
    'ordinary-maven-consumer': 'Ordinary Maven consumer',
    'ordinary-gradle-consumer': 'Ordinary Gradle consumer',
    'dependency-conflict-rejection': 'Conflicting dependency rejection',
    'target-runtime': 'Target interpreter execution',
    'relocated-runtime': 'Runtime after project relocation',
    'target-platform-admission': 'Wheel platform and ABI tag admission',
    'producer-pure-build': 'Nix producer build',
    'incoming-lock': 'Incoming dependency capture',
    'interactive-prefetch': 'Interactive prefetch',
    'incoming-pure-build': 'Nix consumer build',
    'publication-dry-run': 'Local publication dry run',
    'ordinary-consumer': 'Ordinary uv consumer',
    'uploaded-projection-byte-equality': 'Uploaded bytes match the Nix projection',
    'frozen-pylock-fixture-preservation': 'Unchanged frozen pylock fixture',
    'compiled-input-consumption': 'Compiled Nix input consumption',
    'dependency-add-with-nix': 'Native dependency addition with Nix input',
    'dependency-drop-with-nix': 'Native dependency removal with Nix input',
    'ordinary-republisher': 'Ordinary uv republisher',
    'ordinary-own-eviction-conflict': 'Controlled republisher conflict rejection',
    'nix-ordinary-nix-sandwich': 'Nix / ordinary / Nix publication chain',
    'ordinary-nix-ordinary-sandwich': 'Ordinary / Nix / ordinary publication chain',
    'multiple-inputs-shared-leaf': 'Multiple Nix inputs sharing a dependency',
    'multiple-inputs-reversed': 'Reversed Nix input order',
    'competing-input-preserves-state': 'Competing input rejection with unchanged state',
    'native-input-composition': 'Native Nix input composition',
    'nix-input-composition': 'Nix input composition in the sandbox',
    'lock-reproducibility': 'Deterministic relock',
    'relocated-cold-relock': 'Relock after relocation with fresh caches',
    'network-isolated-native-build': 'Native build in an isolated network namespace',
    'ordinary-java-consumer': 'Ordinary Java consumer',
    'native-published-class-byte-equality': 'Published class bytes match native compilation',
    'native-offline-build': 'Offline native build',
    'projected-descriptor-checks': 'Projected dependency descriptors',
    'pom-preservation': 'Unchanged project POM',
    'ordinary-extracted-crate-rebuild': 'Offline extracted-crate rebuild',
    'native-addon-build': 'Native addon build', 'native-addon-load': 'Native addon execution',
    'cdylib-c-caller': 'Shared library with independent C caller',
    'native-tool-selection': 'Native tool selection and rejection',
    'workspace-root-discovery': 'Workspace root discovery',
    'local-publish-dry-run': 'Local publication dry-run',
    'revision-update-invalidation': 'Revision update invalidation',
}
EMPTY = {'defaults': [], 'testedPoints': [], 'supportedRanges': [], 'limitations': [], 'projectSelections': []}
SELECTION_KINDS = {'project-file', 'environment', 'lockfile', 'command-option', 'nix-scope'}


def validate(data):
    if not isinstance(data, dict) or set(data) != set(EMPTY):
        raise ValueError('compatibility requires defaults, testedPoints, supportedRanges limitations and projectSelections')
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
        if set(item) != {'role', 'name', 'version', 'selection', 'systems', 'sourceRevision', 'evidence'}:
            raise ValueError('invalid packaged default')
        component(item); proof(item)
        if not text(item['selection']) or not texts(item['systems']):
            raise ValueError('packaged versions require a toolchain selection and platform scope')
    ids = set()
    for point in data['testedPoints']:
        fields = {'id', 'components', 'system', 'operations', 'sourceRevision', 'evidence', 'notes'}
        if set(point) not in (fields, fields | {'runtimePublication'}):
            raise ValueError('invalid tested version combination')
        proof(point)
        if 'runtimePublication' in point:
            publication = point['runtimePublication']
            if (not isinstance(publication, dict)
                    or set(publication) != {'sourceRevision', 'version', 'proof'}
                    or not text(publication.get('sourceRevision'))
                    or not re.fullmatch(r'[a-f0-9]{40}', publication.get('sourceRevision', ''))
                    or not text(publication.get('version'))
                    or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', publication.get('version', ''))
                    or not text(publication.get('proof'))
                    or not re.fullmatch(r'https://[^\s]+', publication.get('proof', ''))):
                raise ValueError('runtime publication needs an exact source, version and proof')
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
    for item in data['projectSelections']:
        if set(item) != {'role', 'name', 'kind', 'inputs', 'description', 'sourceRevision', 'evidence'}:
            raise ValueError('invalid project-selected version')
        proof(item)
        if (item['role'] not in ROLES or not text(item['name']) or not text(item['description'])
                or not texts(item['inputs']) or item['kind'] not in SELECTION_KINDS):
            raise ValueError('project-selected versions require their actual selection inputs')
    for item in data['limitations']:
        if set(item) != {'text', 'sourceRevision', 'evidence'} or not text(item['text']):
            raise ValueError('invalid version limitation')
        proof(item)
    return data


def cell(value):
    return escape(str(value)).replace('|', '&#124;').replace('\n', ' ')


def evidence(item):
    links = item['evidence']
    url = next((link for link in links if '/actions/runs/' in link),
               next((link for link in links if '/evidence/' in link), links[0]))
    return '[Checks](' + url + ')'


def render_exact_versions(page, contract, heading=True):
    spec = contract['versionCompatibility']
    data = validate(page.get('compatibility', EMPTY))
    lines = ['## ' + spec['title']] if heading else []
    if not any(data.values()):
        lines.append(spec['unknown'])
        return '\n\n'.join(lines)
    packaged = packaged_components(data['defaults'])
    if data['defaults']:
        lines += ['### Packaged versions', render_packaged_components(packaged)]
    definition_items = data['defaults'] + data['projectSelections'] + data['limitations'] + data['supportedRanges']
    if definition_items:
        definitions = list(dict.fromkeys(url for item in definition_items for url in item['evidence']))
        links = ' · '.join('[' + (url.split('/blob/', 1)[1].split('/', 1)[1] if '/blob/' in url else urlsplit(url).netloc) + '](' + url + ')' for url in definitions)
        lines.append('<details markdown="1">\n<summary>Version definitions</summary>\n\n' + links + '\n\n</details>')
    if data['projectSelections']:
        lines += ['### Project-selected versions', '| Component | Selected by |', '|---|---|']
        for item in data['projectSelections']:
            inputs = ', '.join('`' + cell(name) + '`' for name in item['inputs'])
            if item['kind'] == 'nix-scope':
                inputs = 'Nix scope configuration: ' + inputs
            lines.append(f'| {ROLES[item["role"]]}: {cell(item["name"])} | {cell(item["description"])}<br>{inputs} |')
    if data['supportedRanges']:
        lines += ['### Supported ranges']
        for item in data['supportedRanges']:
            lines.append(f'{ROLES[item["role"]]} **{cell(item["name"])}**: {cell(item["range"])} '
                         f'({cell(", ".join(item["systems"]))}). '
                         + cell(item['basis']))
    if data['limitations']:
        lines += ['### Requirements']
        lines += ['- ' + cell(item['text']) for item in data['limitations']]
    return '\n\n'.join(_tables(lines))


USER_ROLES = {'native-tool', 'native-tool-runtime', 'project-runtime', 'compiler'}
JAVA_NAMES = {'JDK', 'OpenJDK', 'Azul Zulu JDK', 'Zulu OpenJDK'}
USER_NAMES = {'Apache Maven': 'Maven', 'Apache Ant': 'Ant', 'Legacy sbt launcher': 'sbt'}
ACCOUNTING_IDENTITIES = {'Bundler::VERSION report', 'Gemcutter',
                         'uv (ordinary republisher)', 'uv (publisher and ordinary consumer)'}


def user_name(name):
    return 'Java' if name in JAVA_NAMES else USER_NAMES.get(name, name)


def user_component(item):
    """Java's release number is useful here; distribution build IDs stay in the matrix."""
    if item['name'] in JAVA_NAMES:
        version = re.match(r'(?:1\.)?(\d+)', item['version'])
        return 'Java', version[1] if version else item['version']
    return user_name(item['name']), item['version']


def version_choices(items):
    def key(version):
        return tuple((0, int(part)) if part.isdigit() else (1, part)
                     for part in re.split(r'(\d+)', version))
    return ', '.join(sorted(set(items), key=key)) or '—'


def verified_platforms(page, data):
    systems = {p['system'] for p in data['testedPoints']}
    # An OS assessment alone does not establish each architecture. Use only
    # bound successful receipts; their IDs have no platform semantics.
    quality = page.get('quality', {})
    review = quality.get('derivationReview', {})
    criteria = review.get('criteria', {})
    directory = Path(__file__).with_name('evidence')
    base = 'https://nix-purifiers.github.io/evidence/'
    for os in ('linux', 'darwin'):
        criterion = criteria.get(os, {})
        if criterion.get('state') != 'met':
            continue
        for identifier in criterion.get('derivations', []):
            receipt = review.get('derivations', {}).get(identifier)
            if (receipt is None or receipt.get('repository') != page['repository']
                    or receipt.get('revision') != quality.get('reviewedRevision')):
                continue
            if receipt.get('kind') != 'native-ci-execution':
                validate_receipt(receipt, directory, base)
            if receipt['system'].endswith('-' + os) and native_success(receipt, directory, base):
                systems.add(receipt['system'])
    return systems


def render_compatibility(page, contract, heading=True):
    """Answer user toolchain choices, keeping the exact inventory in the matrix."""
    data = validate(page.get('compatibility', EMPTY))
    lines = ['## ' + contract['versionCompatibility']['title']] if heading else []
    if not any(data.values()):
        return '\n\n'.join(lines + [contract['versionCompatibility']['unknown']])
    # Keep running the tool separate from compiling/running the project when
    # their choices differ. Equal roles collapse, including tool/compiler Go.
    groups = []
    visible_defaults = [c for c in data['defaults'] if c['role'] in USER_ROLES
                        and c['name'] not in ACCOUNTING_IDENTITIES]
    visible_points = [dict(p, components=[c for c in p['components'] if c['name'] not in ACCOUNTING_IDENTITIES])
                      for p in data['testedPoints']]
    for role in ('native-tool', 'native-tool-runtime', 'compiler', 'project-runtime'):
        names = dict.fromkeys(user_component(c)[0]
                             for c in visible_defaults + [c for p in visible_points for c in p['components']]
                             if c['role'] == role)
        for name in names:
            defaults = [(user_component(c)[1], c['selection'], tuple(c['systems']))
                        for c in visible_defaults if c['role'] == role and user_component(c)[0] == name]
            checked = [tuple(dict.fromkeys(user_component(c)[1] for c in p['components']
                        if c['role'] == role and user_component(c)[0] == name)) for p in visible_points]
            choices = {(v, s) for v, s, _ in defaults}
            group = next((g for g in groups if g['name'] == name and g['checked'] == checked
                          and (not choices or not g['defaults']
                               or choices == {(v, s) for v, s, _ in g['defaults']})), None)
            if group is None:
                group = dict(name=name, roles=[], defaults=[], checked=checked)
                groups.append(group)
            group['roles'].append(role)
            group['defaults'].extend(x for x in defaults if x not in group['defaults'])
    if groups:
        lines += ['| Tool or language | Packaged defaults | Tested versions |', '|---|---|---|']
        all_systems = {s for c in visible_defaults for s in c['systems']}
        for group in groups:
            name = group['name']
            if sum(g['name'] == name for g in groups) > 1:
                labels = {'native-tool': 'tool', 'native-tool-runtime': 'runs the tool',
                          'compiler': 'compiles the project', 'project-runtime': 'runs the project'}
                name += ' (' + ', '.join(labels[r] for r in group['roles']) + ')'
            choices = list(dict.fromkeys((v, s) for v, s, _ in group['defaults']))
            included_choices = []
            for version, selection in choices:
                scope = {s for v, selected, systems in group['defaults']
                         if (v, selected) == (version, selection) for s in systems}
                qualifiers = [selection] if selection != 'default' else []
                if scope != all_systems:
                    qualifiers.append(platform_labels(scope))
                included_choices.append(version + (' (' + '; '.join(qualifiers) + ')' if qualifiers else ''))
            selected = any(user_name(c['name']) == group['name'] and c['role'] in group['roles']
                           for c in data['projectSelections'])
            included = '; '.join(included_choices) or ('Project-selected' if selected else '—')
            tested = version_choices(v for versions in group['checked'] for v in versions)
            lines.append('| ' + cell(name) + ' | ' + cell(included) + ' | ' + cell(tested) + ' |')
    checked = verified_platforms(page, data)
    systems = sorted({s for c in visible_defaults for s in c['systems']} | checked)
    if systems:
        lines += ['### Operating systems and architectures', '| OS | CPU architecture | Packaged toolchain | Recorded workflow |', '|---|---|---|---|']
        packaged = {s for c in visible_defaults for s in c['systems']}
        for system in systems:
            arch, _, os = system.partition('-')
            packaged_status = 'Yes' if system in packaged else 'Not recorded'
            workflow_status = 'Tested' if system in checked else 'Not recorded'
            lines.append('| ' + cell({'linux': 'Linux', 'darwin': 'macOS'}.get(os, os))
                         + ' | ' + cell({'x86_64': 'x86-64', 'aarch64': 'ARM64'}.get(arch, arch)) + ' | ' + packaged_status + ' | ' + workflow_status + ' |')
    selections = [c for c in data['projectSelections'] if c['role'] in USER_ROLES or c['role'] == 'purifier-implementation']
    if selections:
        lines += ['### Choosing versions', '| Component | Selected by |', '|---|---|']
        for item in selections:
            inputs = ', '.join('`' + cell(n) + '`' for n in item['inputs'])
            if item['kind'] == 'nix-scope':
                inputs = 'Nix scope configuration: ' + inputs
            lines.append('| ' + cell(ROLES[item['role']] + ': ' + item['name']) + ' | '
                         + cell(item['description']) + '<br>' + inputs + ' |')
    if data['supportedRanges']:
        lines += ['### Supported ranges']
        lines += ['- ' + cell(c['name'] + ' ' + c['range'] + ': ' + c['basis'])
                  for c in data['supportedRanges'] if c['role'] in USER_ROLES]
    if data['limitations']:
        lines += ['### Requirements'] + ['- ' + cell(c['text']) for c in data['limitations']]
    return '\n\n'.join(_tables(lines))



PLATFORMS = {
    'x86_64-linux': 'Linux x86-64',
    'aarch64-linux': 'Linux ARM64',
    'x86_64-darwin': 'macOS Intel',
    'aarch64-darwin': 'macOS ARM64',
}


def platform_labels(systems):
    order = {system: index for index, system in enumerate(PLATFORMS)}
    return ' · '.join(PLATFORMS.get(system, system) for system in
                      sorted(set(systems), key=lambda system: (order.get(system, len(order)), system)))


def packaged_components(defaults):
    """Show one value for roles sharing the exact selection and platforms."""
    components = {}
    for item in defaults:
        key = (item['selection'], item['name'], item['version'], tuple(sorted(item['systems'])))
        if key not in components:
            components[key] = dict(selection=item['selection'], name=item['name'],
                                   version=item['version'], systems=key[-1], roles=[],
                                   id='packaged-version-' + hashlib.sha256(
                                       json.dumps(key).encode()).hexdigest()[:12])
        if item['role'] not in components[key]['roles']:
            components[key]['roles'].append(item['role'])
    return list(components.values())


def render_packaged_components(components):
    output = []
    for item in components:
        roles = '; '.join(cell(ROLES[role]) for role in item['roles'])
        if item['selection'] != 'default':
            roles += '<small>' + cell(item['selection']) + '</small>'
        platforms = platform_labels(item['systems'])
        output.append('<li class="packaged-version" id="' + item['id'] + '">'
                      '<span class="version-labels"><strong>'
                      + cell(item['name'] + ' ' + item['version']) + '</strong> <span>'
                      + roles + '</span> <span>' + cell(platforms) + '</span></span></li>')
    return '<ul class="packaged-versions">\n' + '\n'.join(output) + '\n</ul>'


def packaged_match(component, systems, packaged):
    """Link a matching version; keep each test's source and coverage separate."""
    role, name, version = component
    matches = [item for item in packaged if role in item['roles']
               and item['name'] == name and item['version'] == version
               and set(systems) <= set(item['systems'])]
    defaults = [item for item in matches if item['selection'] == 'default']
    if len(defaults) == 1:
        return defaults[0]
    return matches[0] if len(matches) == 1 else None


def component_label(component, match=None):
    _, name, version = component
    if match:
        return '<a href="#' + match['id'] + '">' + cell(name) + ' (packaged version)</a>'
    return cell(name + ' ' + version)


def tested_combinations(points, packaged=()):
    """Group only identical complete toolchains; keep each test's scope intact."""
    combinations = {}
    for point in points:
        key = tuple(sorted((c['role'], c['name'], c['version']) for c in point['components']))
        combinations.setdefault(key, []).append(point)
    output = []
    for components, checks in combinations.items():
        systems = {point['system'] for point in checks}
        matches = {component: packaged_match(component, systems, packaged) for component in components}
        tools = ' · '.join(component_label(component, matches[component])
                           for component in components if component[0] == 'native-tool')
        formats = ' · '.join(component_label(component, matches[component])
                             for component in components if component[0] == 'native-format')
        if formats:
            tools += '<small>' + formats + '</small>'
        runtimes = {}
        for role, name, version in components:
            if role not in ('native-tool', 'host-helper', 'native-format',
                            'publisher-tool', 'publisher-runtime', 'publisher-helper'):
                runtimes.setdefault((name, version), []).append((role, name, version))
        runtime_labels = []
        for (name, version), group in runtimes.items():
            refs = [matches[c] for c in group]
            match = refs[0] if all(ref is not None and ref['id'] == refs[0]['id'] for ref in refs) else None
            native_match = matches.get(('native-tool', name, version))
            roles = [ROLES[c[0]] for c in group]
            if match and native_match and match['id'] == native_match['id']:
                label = cell('Also ' + ', '.join(roles).lower())
            else:
                label = component_label(group[0], match)
                if len(runtimes) > 1:
                    label += ' (' + cell(', '.join(roles)) + ')'
            runtime_labels.append(label)
        runtime = ' · '.join(runtime_labels)
        if any(c[0].startswith('publisher-') for c in components):
            runtime += '<small>Separate publisher SDK; see full toolchain roles</small>'
        platforms = platform_labels(point['system'] for point in checks)
        output += ['<details class="tested-combination" markdown="1">',
                   '<summary><span class="tested-combination-labels version-labels"><strong>' + tools
                   + '</strong> <span>' + runtime + '</span> <span>' + cell(platforms)
                   + '</span></span></summary>',
                   '<details markdown="1">\n<summary>Full toolchain roles</summary>\n',
                   '\n'.join('- ' + cell(ROLES[c[0]] + ': ') + component_label(c, matches[c])
                             for c in components), '</details>']
        for point in checks:
            output += ['**' + cell(PLATFORMS.get(point['system'], point['system']))
                       + ' (`' + cell(point['system']) + '`)** — ' + evidence(point),
                       '**Checked operations**',
                       '<ul class="tested-operations">'
                       + ''.join('<li>' + cell(OPERATIONS.get(op, op.replace('-', ' '))) + '</li>'
                                 for op in point['operations']) + '</ul>',
                       '<details markdown="1">\n<summary>Limits and source evidence</summary>\n']
            output += ['- ' + cell(note) for note in point['notes']]
            if 'runtimePublication' in point:
                publication = point['runtimePublication']
                output += ['Released purifier runtime ' + publication['version'] + ' at `'
                           + publication['sourceRevision'] + '` ([provenance]('
                           + publication['proof'] + ')).']
            output += ['Source revision `' + point['sourceRevision'] + '`.',
                       ' · '.join('[' + ('CI run' if '/actions/runs/' in url else 'Source')
                                  + '](' + url + ')' for url in point['evidence']), '</details>']
        output.append('</details>')
    return '\n\n'.join(output)

def _tables(lines):
    """Keep Markdown table rows contiguous and paragraphs separated."""
    result = []
    for line in lines:
        if result and line.startswith('|') and result[-1].startswith('|'):
            result[-1] += '\n' + line
        else:
            result.append(line)
    return result
