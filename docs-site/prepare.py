"""Prepare a purifier README for its GitHub Pages documentation site."""
import argparse
import json
from pathlib import Path
import re
from content import audit, feature_matrix, render, source_links
from theme import install_theme
from review import verify
from reference import guide_plan, reference_text

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repository', required=True)
parser.add_argument('--readme', default='README.md', type=Path)
parser.add_argument('--output', default='.pages-source', type=Path)
parser.add_argument('--content', type=Path,
                    help='Structured project JSON (defaults to docs-site/page.json beside README)')
parser.add_argument('--catalog', type=Path,
                    help='Nix documentation export containing catalog and contract')
parser.add_argument('--model', action='store_true', help='Use the bundled, validated model export')
parser.add_argument('--check-source', type=Path, help='Verify this checkout matches the reviewed implementation')
args = parser.parse_args()
if not re.fullmatch(r'[\w.-]+/[\w.-]+', args.repository):
    parser.error('repository must be owner/name')
theme = Path(__file__).parent
if args.check_source:
    try:
        verify(args.repository, args.check_source)
    except ValueError as error:
        parser.error(str(error))
if args.model and args.repository != 'nix-purifiers/purifier':
    args.catalog = args.catalog or theme / 'catalog.json'
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
    if args.repository == 'nix-purifiers/purifier':
        text = reference_text(args.repository, text)
source = args.output
install_theme(source)
if differences is not None:
    report = {'repository': args.repository, **audit(page, differences)}
    (source / 'content-variations.json').write_text(json.dumps(report, indent=2) + '\n')
    (source / 'system.json').write_text(json.dumps(page, indent=2) + '\n')
    (source / 'features.md').write_text('---\nlayout: default\n---\n\n' + feature_matrix(page, contract))
    reference = theme / 'references' / (args.repository.split('/')[1] + '.md')
    if reference.exists():
        (source / 'guide-structure.json').write_text(json.dumps(guide_plan(args.repository, reference.read_text()), indent=2) + '\n')
        (source / 'reference.md').write_text('---\nlayout: default\n---\n\n' + source_links(reference_text(args.repository, reference.read_text(), page), args.repository))
else:
    for filename in ('content-variations.json', 'system.json', 'features.md', 'reference.md', 'guide-structure.json'):
        (source / filename).unlink(missing_ok=True)
# Keep source links useful outside GitHub, including images.
text = source_links(text, args.repository)
(source / 'index.md').write_text('---\nlayout: default\n---\n\n' + text)
(source / '_config.yml').write_text(json.dumps({
    'title': args.repository.split('/')[1],
    'description': 'Native development with locked, Nix-resolved dependencies',
    'repository': args.repository,
    'feature_matrices': {args.repository: '/features.html'} if differences is not None else {},
    'url': 'https://nix-purifiers.github.io',
    'baseurl': '/' + args.repository.split('/')[1],
    'markdown': 'kramdown',
    'kramdown': {'input': 'GFM'},
}))
