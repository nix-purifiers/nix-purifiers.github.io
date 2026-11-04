"""Render detailed guides in a shared structure, retaining native explanations."""
import json
import re
from pathlib import Path


def source_sections(text):
    """Read source headings without treating fenced examples as sections."""
    intro, sections, current = [], [], None
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        heading = re.match(r'^##\s+(.+?)\s*$', line) if fence is None else None
        if heading:
            current = [heading[1], []]
            sections.append(current)
        elif current is None:
            intro.append(line)
        else:
            current[1].append(line)
    introduction = re.sub(r'^#\s+[^\n]+\n', '', ''.join(intro)).strip()
    return introduction, [(title, ''.join(lines).strip()) for title, lines in sections]


def guide_plan(repository, text, plan=None):
    name = repository.split('/')[1]
    if plan is None:
        plan = json.loads((Path(__file__).parent / 'guides' / (name + '.json')).read_text())
    contract = json.loads((Path(__file__).parent / 'guide-contract.json').read_text())
    if set(plan) != {'version', 'repository', 'introduction', 'sections'} or plan['repository'] != repository:
        raise ValueError(f'{name}: invalid full-guide plan')
    if set(plan['sections']) != {s['id'] for s in contract['sections']}:
        raise ValueError(f'{name}: every full-guide section requires a decision')
    introduction = plan['introduction']
    if (set(introduction) != {'section', 'omitSummary'}
            or introduction['section'] not in {None, *plan['sections']}
            or not isinstance(introduction['omitSummary'], bool)):
        raise ValueError(f'{name}: invalid introduction placement')
    if introduction['section'] and 'omit' in plan['sections'][introduction['section']]:
        raise ValueError(f'{name}: introduction targets an omitted section')
    actual = [title for title, _ in source_sections(text)[1]]
    selected = []
    for identifier, section in plan['sections'].items():
        if 'omit' in section:
            if set(section) != {'omit'} or not section['omit'].strip():
                raise ValueError(f'{name}.{identifier}: omissions require a reason')
        elif set(section) <= {'sourceSections', 'facts'}:
            selected.extend(section.get('sourceSections', []))
            if set(section.get('facts', [])) - {'platforms', 'platform_notes'}:
                raise ValueError(f'{name}.{identifier}: unknown detailed-guide facts')
        else:
            raise ValueError(f'{name}.{identifier}: unexpected guide fields')
    if len(actual) != len(set(actual)) or sorted(selected) != sorted(actual):
        raise ValueError(f'{name}: each source section must be assigned exactly once')
    return plan


def slug(title):
    return re.sub(r'\s+', '-', re.sub(r'[^\w -]', '', title.lower()))


def deeper_headings(text):
    lines, fence = [], None
    for line in text.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        if fence is None and re.match(r'^#{3,5} ', line):
            line = '#' + line
        lines.append(line)
    return '\n'.join(lines)


def detailed_guide(repository, text, page, plan=None):
    theme = Path(__file__).parent
    contract = json.loads((theme / 'guide-contract.json').read_text())
    overview = json.loads((theme / 'contract.json').read_text())
    titles = {s['id']: s['title'] for s in overview['sections']}
    plan = guide_plan(repository, text, plan)
    introduction, source = source_sections(text)
    source = dict(source)
    if plan['introduction']['omitSummary']:
        introduction = introduction.partition('\n\n')[2].strip()
    name = repository.split('/')[1]
    sections = []
    for specification in contract['sections']:
        identifier = specification['id']
        decision = plan['sections'][identifier]
        if 'omit' in decision:
            continue
        title = titles[specification['titleFrom']] if 'titleFrom' in specification else specification['title']
        blocks = []
        if introduction and plan['introduction']['section'] == identifier:
            blocks.append((contract['introductionHeading'], introduction, False))
        for original in decision.get('sourceSections', []):
            body = source[original]
            # The overview owns the initial command sequence. Remove it here
            # only when it is exactly the same; retain distinct setup examples.
            if original == 'Quickstart' and page.get('values', {}).get('quickstart'):
                match = re.search(r'(?m)^```[^\n]*\n(.*?)^```\s*$', body, re.DOTALL)
                if match and match[1].strip() == page['values']['quickstart'].strip():
                    body = body[:match.start()] + contract['quickstartPointer'] + body[match.end():]
                    body = re.sub(r'^From the project root:\s*', '', body)
            blocks.append((original, body, True))
        for fact_name in decision.get('facts', []):
            fact = page['facts'][fact_name]
            if fact['state'] != 'known':
                raise ValueError(f'{name}: guide cannot render unknown fact {fact_name}')
            value = fact['value']
            body = ('Target systems: ' + ', '.join(value) + '.') if fact_name == 'platforms' else '\n\n'.join(value)
            blocks.append((contract['factHeadings'][fact_name], body, False))
        if not blocks:
            raise ValueError(f'{name}.{identifier}: empty detailed-guide section')
        chunks = []
        canonical = slug(title)
        for original, body, is_source in blocks:
            legacy = slug(original)
            if len(blocks) > 1:
                chunks.append('### ' + original + '\n\n' + deeper_headings(body))
            else:
                if is_source and legacy != canonical:
                    chunks.append(f'<a id="{legacy}"></a>')
                chunks.append(body)
        sections.append((title, '\n\n'.join(chunks)))
    lines = ['# ' + name + ' full guide', contract['introduction'],
             '## ' + contract['contentsTitle'],
             '\n'.join(f'- [{title}](#{slug(title)})' for title, _ in sections)]
    lines.extend('## ' + title + '\n\n' + body for title, body in sections)
    return '\n\n'.join(lines) + '\n'


def reference_text(repository, text, page=None, plan=None):
    if page:
        return detailed_guide(repository, text, page, plan)
    # Retained guides use the same visible section title as modeled pages.
    # Keep legacy fragment IDs so links into the original guide still work.
    contract = json.loads((Path(__file__).parent / 'contract.json').read_text())
    title = next(section['title'] for section in contract['sections'] if section['id'] == 'editor')
    def heading(match):
        old = match[1].lower().replace(' ', '-')
        return f'<a id="{old}"></a>\n\n## {title}'
    text = re.sub(r'^## (Editors?(?: and (?:compiler|shells))?)[ \t]*$', heading, text, flags=re.MULTILINE)
    if repository == 'nix-purifiers/purifier':
        data = json.loads((Path(__file__).parent.parent / 'model/library.json').read_text())
        paragraphs = ['Target systems: ' + ', '.join(data['platforms']) + '.']
        paragraphs += data['limitations'] + data['validation']
    elif page:
        notes = page['facts'].get('platform_notes', {})
        paragraphs = notes.get('value', []) if notes.get('state') == 'known' else []
    else:
        paragraphs = []
    if not paragraphs:
        return text
    marker = text.find('\n## ')
    addition = '\n\n## Platform scope\n\n' + '\n\n'.join(paragraphs) + '\n'
    return text[:marker] + addition + text[marker:] if marker >= 0 else text + addition
