"""Validate and render structured project copy using the shared section contract."""
import re
import shlex
from html import escape
from compatibility import render_compatibility


def source_links(text, repository, revision='main'):
    """Resolve README-relative links against the source repository."""
    return re.sub(r'\]\((?![a-zA-Z][\w+.-]*:|#|/|(?:reference|features)\.html(?:[#?)]|$))([^)]+)\)',
                  lambda m: f'](https://github.com/{repository}/blob/{revision}/{m[1]})', text)


def audit(page, variations):
    """Describe copy selections, local differences, and unresolved behavior."""
    return {
        'selected_templates': {key: entry['use'] for key, entry in page['sections'].items() if 'use' in entry},
        'variations': variations,
        'unresolved': {key: fact for key, fact in page['facts'].items() if fact['state'] != 'known'},
    }


def feature_matrix(page, contract):
    """Render a separate reference table from the authoritative declared facts."""
    project = page['repository'].split('/')[1]
    lines = [f'# {project} feature matrix',
             'Declared behavior and capabilities. [Back to documentation](./).',
             '| Feature | Behavior |', '| --- | --- |']
    def cell(value):
        return escape(value).replace('|', '&#124;').replace('\n', '<br>')
    for key, definition in contract['facts'].items():
        if not definition.get('matrix', True):
            continue
        fact = page['facts'][key]
        if fact['state'] == 'known':
            value = fact['value']
            if isinstance(value, list):
                value = [definition.get('itemLabels', {}).get(item, item) for item in value]
            behavior = ('Supported' if value else 'Not supported') if isinstance(value, bool) else (
                ', '.join(value) if isinstance(value, list) else definition.get('valueLabels', {}).get(value, value))
        else:
            behavior = ('Unknown' if fact['state'] == 'unknown' else 'Not applicable') + ': ' + fact['reason']
        label = definition.get('label', key.replace('_', ' ').capitalize())
        description = definition.get('description', '')
        lines.append(f'| <span title="{escape(description, quote=True)}">{cell(label)}</span> | '
                     f'{cell(behavior)} |')
    return '\n\n'.join(lines[:2]) + '\n\n' + '\n'.join(lines[2:]) + ('\n\nFor tested versions and requirements, see [Version compatibility](./#version-compatibility).\n' if 'versionCompatibility' in contract else '\n')


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be nonempty text')
    return value


def render(page, contract):
    """Return Markdown and an audit of additions, replacements and omissions.

    Shared prose is selected by name; local prose cannot silently overwrite it.
    Every contract section requires an explicit decision from the project.
    """
    required = {'version', 'repository', 'summary', 'facts', 'sections', 'operations'}
    if not required <= set(page) or set(page) - required - {'values', 'reviewedRevision', 'compatibility'} or page['version'] != 1:
        raise ValueError('expected version 1, repository, summary, facts, sections and operations')
    repository = nonempty(page['repository'], 'repository')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repository):
        raise ValueError('repository must be owner/name')
    project = repository.split('/')[1]
    if project in {'.', '..'}:
        raise ValueError('repository name cannot be a path component')
    summary = nonempty(page['summary'], 'summary')
    facts = page['facts']
    definitions = contract.get('facts', {})
    if not isinstance(facts, dict) or set(facts) != set(definitions):
        raise ValueError(f'facts must be exactly: {", ".join(sorted(definitions))}')
    for key, definition in definitions.items():
        fact = facts[key]
        if not isinstance(fact, dict):
            raise ValueError(f'{key}: expected a fact object')
        if fact.get('state') == 'known':
            if not {'state', 'value'} <= set(fact) or set(fact) - {'state', 'value', 'sources'}:
                raise ValueError(f'{key}: known facts require a value and may include sources')
            value = fact['value']
            if definition['type'] == 'string':
                nonempty(value, key)
            elif definition['type'] == 'strings':
                if not isinstance(value, list) or not value:
                    raise ValueError(f'{key}: expected a nonempty list')
                for item in value:
                    nonempty(item, key)
                    if 'itemsEnum' in definition and item not in definition['itemsEnum']:
                        raise ValueError(f'{key}: unknown item {item!r}')
            elif definition['type'] == 'boolean':
                if not isinstance(value, bool):
                    raise ValueError(f'{key}: expected a boolean')
            else:
                raise ValueError(f'{key}: unsupported fact type')
            if 'enum' in definition and value not in definition['enum']:
                raise ValueError(f'{key}: expected one of {definition["enum"]}')
            if not isinstance(fact.get('sources', []), list):
                raise ValueError(f'{key}: sources must be a list')
            for reference in fact.get('sources', []):
                nonempty(reference, f'{key}.sources')
        elif fact.get('state') in {'unknown', 'not-applicable'}:
            if set(fact) != {'state', 'reason'}:
                raise ValueError(f'{key}: provide state and reason')
            nonempty(fact['reason'], f'{key}.reason')
        else:
            raise ValueError(f'{key}: expected known, unknown or not-applicable')

    def substitute(match):
        key = match[1]
        if key not in facts or facts[key]['state'] != 'known':
            raise ValueError(f'cannot render unknown or missing fact {key}')
        value = facts[key]['value']
        if isinstance(value, list):
            value = [definitions[key].get('itemLabels', {}).get(item, item) for item in value]
        if isinstance(value, bool):
            return 'supported' if value else 'not supported'
        return ', '.join(value) if isinstance(value, list) else definitions[key].get('valueLabels', {}).get(value, value)

    def command(match):
        name = match[1]
        recipe = page['operations'].get(name)
        if recipe is None or recipe['state'] != 'available':
            raise ValueError(f'cannot document unavailable operation {name}')
        arguments = [recipe['capability']]
        for argument in recipe['arguments']:
            if isinstance(argument, str):
                arguments.append(argument)
            elif set(argument) == {'binding'}:
                arguments.append('<' + argument['binding'] + '>')
            elif argument != {'splice': 'arguments'}:
                raise ValueError(f'{name}: invalid command argument')
        return shlex.join(arguments)
    sections = page['sections']
    expected = {s['id'] for s in contract['sections']}
    if not isinstance(sections, dict) or set(sections) != expected:
        raise ValueError(f'sections must be exactly: {", ".join(sorted(expected))}')
    output = [f'# {project}', summary]
    differences = []
    for spec in contract['sections']:
        key = spec['id']
        entry = sections[key]
        if not isinstance(entry, dict):
            raise ValueError(f'{key}: expected an object')
        modes = set(entry) & {'use', 'replace', 'omit'}
        if len(modes) != 1:
            raise ValueError(f'{key}: choose exactly one of use, replace, omit')
        mode = next(iter(modes))
        allowed = {'use', 'details', 'blocks'} if mode == 'use' else (
            {'replace', 'reason'} if mode == 'replace' else {'omit'})
        if set(entry) - allowed:
            raise ValueError(f'{key}: unexpected fields {sorted(set(entry) - allowed)}')
        value = nonempty(entry[mode], f'{key}.{mode}')
        if mode == 'omit':
            differences.append({'section': key, 'kind': 'omitted', 'reason': value})
            continue
        if mode == 'replace':
            reason = nonempty(entry.get('reason'), f'{key}.reason')
            body = value
            differences.append({'section': key, 'kind': 'replaced', 'reason': reason})
        else:
            variants = spec['shared']
            if value not in variants:
                raise ValueError(f'{key}: unknown shared copy {value!r}')
            for fact_key, required in spec.get('requires', {}).get(value, {}).items():
                fact = facts.get(fact_key, {})
                choices = required if isinstance(required, list) else [required]
                if fact.get('state') != 'known' or fact.get('value') not in choices:
                    raise ValueError(f'{key}: shared copy requires {fact_key} in {choices}')
            template = variants[value]
            blocks = [{'id': 'main', 'text': template}] if isinstance(template, str) else template
            if not isinstance(blocks, list) or not blocks:
                raise ValueError(f'{key}: expected nonempty template blocks')
            identifiers = [block['id'] for block in blocks]
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f'{key}: block names must be unique')
            overrides = entry.get('blocks', {})
            if not isinstance(overrides, dict) or set(overrides) - set(identifiers):
                raise ValueError(f'{key}: unknown block names')
            pieces = []
            for block in blocks:
                identifier = block['id']
                prose = overrides.get(identifier, {})
                if not isinstance(prose, dict) or set(prose) - {'before', 'extra-explanation', 'after'}:
                    raise ValueError(f'{key}.{identifier}: unknown prose slots')
                conditions = block.get('when', {})
                required_known = block.get('whenKnown', [])
                if (set(conditions) | set(required_known)) - set(facts):
                    raise ValueError(f'{key}.{identifier}: unknown condition facts')
                active = all(facts[k]['state'] == 'known' for k in required_known) and all(facts[k]['state'] == 'known' and facts[k]['value'] in (
                    expected if isinstance(expected, list) else [expected])
                    for k, expected in conditions.items())
                if not active:
                    if prose:
                        raise ValueError(f'{key}.{identifier}: prose targets an inactive block')
                    continue
                if 'before' in prose:
                    pieces.append(nonempty(prose['before'], f'{key}.{identifier}.before'))
                pieces.append(nonempty(block['text'], f'{key}.{identifier}.text'))
                for slot in ('extra-explanation', 'after'):
                    if slot in prose:
                        pieces.append(nonempty(prose[slot], f'{key}.{identifier}.{slot}'))
                for slot, text in prose.items():
                    differences.append({'section': key, 'block': identifier, 'kind': slot, 'text': text})
            body = '\n\n'.join(pieces)
            if 'details' in entry:
                details = nonempty(entry['details'], f'{key}.details')
                body += '\n\n' + details
                differences.append({'section': key, 'kind': 'extended', 'details': details})
        # Substitute explicit tokens after composing shared and local prose.
        body = body.replace('{project}', project).replace('{repository}', repository)
        body = re.sub(r'\{facts\.([a-z_]+)\}', substitute, body)
        body = re.sub(r'\{commands\.([a-z_-]+)\}', command, body)
        def inject_value(match):
            name = match[1]
            if name not in page.get('values', {}):
                raise ValueError(f'{key}: missing presentation value {name}')
            return nonempty(page['values'][name], f'values.{name}')
        body = re.sub(r'\{values\.([a-z_]+)\}', inject_value, body)
        if re.search(r'^#{1,2}\s', body, re.MULTILINE):
            raise ValueError(f'{key}: use level-three headings inside sections')
        if body.strip():
            output.append(f'## {spec["title"]}\n\n{body}')
    if 'versionCompatibility' in contract:
        section = render_compatibility(page, contract)
        position = next((i + 1 for i, block in enumerate(output) if block.startswith('## Quickstart\n')), 2)
        output.insert(position, section)
    return '\n\n'.join(output) + '\n', differences
