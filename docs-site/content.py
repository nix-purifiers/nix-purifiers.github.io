"""Validate and render structured project copy using the shared section contract."""
import re
import shlex


def source_links(text, repository):
    """Resolve README-relative links against the source repository."""
    return re.sub(r'\]\((?![a-zA-Z][\w+.-]*:|#|/)([^)]+)\)',
                  lambda m: f'](https://github.com/{repository}/blob/main/{m[1]})', text)


def audit(page, variations):
    """Describe copy selections, local differences, and unresolved behavior."""
    return {
        'selected_templates': {key: entry['use'] for key, entry in page['sections'].items() if 'use' in entry},
        'variations': variations,
        'unresolved': {key: fact for key, fact in page['facts'].items() if fact['state'] != 'known'},
    }


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be nonempty text')
    return value


def render(page, contract):
    """Return Markdown and an audit of additions, replacements and omissions.

    Shared prose is selected by name; local prose cannot silently overwrite it.
    Every contract section requires an explicit decision from the project.
    """
    if set(page) != {'version', 'repository', 'summary', 'facts', 'sections', 'operations'} or page['version'] != 1:
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
            if set(fact) != {'state', 'value', 'sources'}:
                raise ValueError(f'{key}: known facts require value and sources')
            value = fact['value']
            if definition['type'] == 'string':
                nonempty(value, key)
            elif definition['type'] == 'strings':
                if not isinstance(value, list) or not value:
                    raise ValueError(f'{key}: expected a nonempty list')
                for item in value:
                    nonempty(item, key)
            else:
                raise ValueError(f'{key}: unsupported fact type')
            if 'enum' in definition and value not in definition['enum']:
                raise ValueError(f'{key}: expected one of {definition["enum"]}')
            if not isinstance(fact['sources'], list) or not fact['sources']:
                raise ValueError(f'{key}: provide source references')
            for reference in fact['sources']:
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
        return ', '.join(value) if isinstance(value, list) else value

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
        allowed = {'use', 'details'} if mode == 'use' else (
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
            body = nonempty(variants[value], f'{key}.shared.{value}')
            # Only these explicit tokens are substituted; code braces stay literal.
            body = body.replace('{project}', project).replace('{repository}', repository)
            if 'details' in entry:
                details = nonempty(entry['details'], f'{key}.details')
                body += '\n\n' + details
                differences.append({'section': key, 'kind': 'extended', 'details': details})
        body = re.sub(r'\{facts\.([a-z_]+)\}', substitute, body)
        body = re.sub(r'\{commands\.([a-z_-]+)\}', command, body)
        if re.search(r'^#{1,2}\s', body, re.MULTILINE):
            raise ValueError(f'{key}: use level-three headings inside sections')
        output.append(f'## {spec["title"]}\n\n{body}')
    return '\n\n'.join(output) + '\n', differences
