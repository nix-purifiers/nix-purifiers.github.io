"""Assign whole source sections or explicit Markdown blocks without losing prose."""
import re


def markdown_blocks(text):
    result, lines, fence = [], [], None
    for line in text.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        if not line.strip() and fence is None:
            if lines:
                result.append('\n'.join(lines))
                lines = []
        else:
            lines.append(line)
    if lines:
        result.append('\n'.join(lines))
    return result


def validate_assignments(introduction, source, plan, selections):
    titles = [title for title, _ in source]
    if len(titles) != len(set(titles)):
        raise ValueError('Each source section must be assigned exactly once; duplicate heading')
    sections = dict(source)
    if plan['introduction']['omitSummary']:
        introduction = introduction.partition('\n\n')[2].strip()
    uses_intro = any(isinstance(item, dict) and item.get('heading') == '@introduction' for item in selections)
    if uses_intro:
        if plan['introduction']['section'] is not None:
            raise ValueError('Introduction cannot be assigned both wholly and in blocks')
        sections['@introduction'] = introduction
    elif introduction and plan['introduction']['section'] is None:
        raise ValueError('Introduction requires explicit placement')
    expected = {(heading, index) for heading, text in sections.items()
                for index in range(len(markdown_blocks(text)))}
    assigned = []
    selected_headings = set()
    for item in selections:
        if isinstance(item, str):
            if item not in sections:
                raise ValueError('Each source section must be assigned exactly once; unknown heading ' + item)
            indices = range(len(markdown_blocks(sections[item])))
            heading = item
        elif isinstance(item, dict) and set(item) == {'heading', 'blocks'}:
            heading, indices = item['heading'], item['blocks']
            if heading not in sections or not isinstance(indices, list) or not indices:
                raise ValueError('Source fragments require a known heading and nonempty block indices')
            if any(type(index) is not int or index < 0 for index in indices):
                raise ValueError('Source block indices must be nonnegative integers')
        else:
            raise ValueError('Source selections require a heading or explicit heading/blocks')
        selected_headings.add(heading)
        assigned.extend((heading, index) for index in indices)
    if set(assigned) != expected or len(assigned) != len(set(assigned)) or selected_headings != set(sections):
        raise ValueError('Each source section must be assigned exactly once, including all prose blocks')


def select_block(sections, selector):
    if isinstance(selector, str):
        return selector, sections[selector], False
    heading = selector['heading']
    blocks = markdown_blocks(sections[heading])
    return heading, '\n\n'.join(blocks[index] for index in selector['blocks']), True
