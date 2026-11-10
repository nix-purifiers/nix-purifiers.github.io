"""One central documentation namespace, independent of project Pages hosting."""
import json
import re
from html import escape
from pathlib import Path

ORIGIN = 'https://nix-purifiers.github.io'


def validate_inputs(documentation):
    """Use the existing pinned source manifest; never ingest live producer state."""
    manifest = json.loads((Path(__file__).resolve().parents[1] / 'model/repositories.json').read_text())
    catalog = documentation['catalog']
    if set(catalog) != set(manifest) - {'purifier'}:
        raise ValueError('central documentation must cover the complete pinned source manifest')
    for name, page in catalog.items():
        source = manifest[name]
        if page.get('repository') != source['repository'] or page.get('reviewedRevision') != source['revision']:
            raise ValueError(f'{name}: documentation must match the pinned source identity')
    return manifest


def project_root(repository):
    return '/projects/' + repository.split('/')[1] + '/'


def canonicalize(text, names):
    # Rewrite documentation entry points only. Native Maven/artifact paths and
    # source links remain exactly as supplied by their owning project.
    alternatives = '|'.join(re.escape(name) for name in names)
    return re.sub(r'''(?P<link>href=["']|\]\()(?P<origin>https://nix-purifiers\.github\.io)?/(?P<name>''' + alternatives +
                  r')/(?P<page>(?:index|reference|features)\.html)?(?=["\s)#?<>]|$)',
                  lambda m: m['link'] + (m['origin'] or '') + '/projects/' + m['name'] + '/' + (m['page'] or ''), text)


def entry(repository, filename='index.html', snapshot=None, reference=None):
    url = ORIGIN + project_root(repository) + ('' if filename == 'index.html' else filename)
    title = {'index.html': 'Documentation', 'reference.html': 'Full guide',
             'features.html': 'Feature matrix'}[filename]
    text = ('---\nlayout: default\ncanonical_url: ' + json.dumps(url) +
            '\n---\n\n# ' + title + '\n\n[' + title + '](' + url +
            ') is maintained in the central documentation site.\n')
    if snapshot:
        text += ('\n[' + snapshot + '](' + snapshot + ') is a revision-bound documentation snapshot, '
                 'not the current documentation authority.\n')
    if reference:
        # Retain incoming legacy guide fragments as links to the same central
        # anchors, without publishing another copy of the guide or its claims.
        from reference import slug
        visible = []
        fence = None
        for line in reference.splitlines():
            marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
            if marker:
                token = marker[1]
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = None
                continue
            if fence is None:
                visible.append(line)
        reference = '\n'.join(visible)
        anchors = set(re.findall(r'<a id="([^"]+)"', reference))
        anchors.update(slug(title.strip()) for title in re.findall(r'^#{1,6}\s+(.+)$', reference, re.M))
        for anchor in sorted(anchors):
            text += f'\n<a id="{escape(anchor, quote=True)}"></a>\n[Continue in the full guide]({url}#{anchor}).\n'
    return text
