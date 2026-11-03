"""Preserve native guides while adding structured platform scope."""
import json
from pathlib import Path


def reference_text(repository, text, page=None):
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
