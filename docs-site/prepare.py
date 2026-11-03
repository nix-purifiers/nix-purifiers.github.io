"""Prepare a purifier README for its GitHub Pages documentation site."""
import argparse
import json
from pathlib import Path
import re
from content import audit, feature_matrix, render, source_links
from theme import install_theme

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repository', required=True)
parser.add_argument('--readme', default='README.md', type=Path)
parser.add_argument('--output', default='.pages-source', type=Path)
parser.add_argument('--content', type=Path,
                    help='Structured project JSON (defaults to docs-site/page.json beside README)')
parser.add_argument('--catalog', type=Path,
                    help='Nix documentation export containing catalog and contract')
args = parser.parse_args()
if not re.fullmatch(r'[\w.-]+/[\w.-]+', args.repository):
    parser.error('repository must be owner/name')
theme = Path(__file__).parent
content_path = args.content or args.readme.parent / 'docs-site' / 'page.json'
differences = None
if args.catalog or args.content is not None or content_path.exists():
    if args.catalog:
        documentation = json.loads(args.catalog.read_text())
        name = args.repository.split('/')[1]
        if name not in documentation['catalog']:
            parser.error(f'{args.repository} is not in the catalog')
        page = documentation['catalog'][name]
        contract = documentation['contract']
    else:
        page = json.loads(content_path.read_text())
        contract = json.loads((theme / 'contract.json').read_text())
        contract['facts'] = json.loads((theme.parent / 'model/contract.json').read_text())['facts']
    if page.get('repository') != args.repository:
        parser.error('content repository does not match --repository')
    try:
        text, differences = render(page, contract)
    except ValueError as error:
        parser.error(str(error))
else:
    text = args.readme.read_text()
source = args.output
install_theme(source)
if differences is not None:
    report = {'repository': args.repository, **audit(page, differences)}
    (source / 'content-variations.json').write_text(json.dumps(report, indent=2) + '\n')
    (source / 'system.json').write_text(json.dumps(page, indent=2) + '\n')
    (source / 'features.md').write_text('---\nlayout: default\n---\n\n' + feature_matrix(page, contract))
else:
    for filename in ('content-variations.json', 'system.json', 'features.md'):
        (source / filename).unlink(missing_ok=True)
# Keep source links useful outside GitHub, including images.
text = source_links(text, args.repository)
matrix_metadata = '\nfeature_matrix: /features.html' if differences is not None else ''
(source / 'index.md').write_text('---\nlayout: default' + matrix_metadata + '\n---\n\n' + text)
(source / '_config.yml').write_text(json.dumps({
    'title': args.repository.split('/')[1],
    'description': 'Native development with locked, Nix-resolved dependencies',
    'repository': args.repository,
    'url': 'https://nix-purifiers.github.io',
    'baseurl': '/' + args.repository.split('/')[1],
    'markdown': 'kramdown',
    'kramdown': {'input': 'GFM'},
}))
