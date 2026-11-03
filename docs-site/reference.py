"""Preserve native guides while adding structured platform scope."""
import json
import re
from pathlib import Path


def reference_text(repository, text, page=None):
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
