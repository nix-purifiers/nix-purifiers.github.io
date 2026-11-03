"""Prepare a purifier README for its GitHub Pages documentation site."""
import argparse
import json
from pathlib import Path
import re
from content import audit, feature_matrix, render, source_links
from theme import install_theme
from review import resolve_review
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
review = None
if args.check_source:
    try:
        review = resolve_review(args.repository, args.check_source)
    except ValueError as error:
        parser.error(str(error))
if review is not None and review.page is not None and not args.model:
    parser.error('reviewed source variants require --model')
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
        page = review.page if review is not None and review.page is not None else documentation['catalog'][name]
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
    guide = review.reference if review is not None and review.reference is not None else reference.read_text() if reference.exists() else None
    revision = review.revision if review is not None and review.page is not None else 'main'
    plan = review.guide_plan if review is not None else None
    if guide is not None:
        (source / 'guide-structure.json').write_text(json.dumps(guide_plan(args.repository, guide, plan), indent=2) + '\n')
        (source / 'reference.md').write_text('---\nlayout: default\n---\n\n' + source_links(reference_text(args.repository, guide, page, plan), args.repository, revision))
else:
    for filename in ('content-variations.json', 'system.json', 'features.md', 'reference.md', 'guide-structure.json'):
        (source / filename).unlink(missing_ok=True)
# Keep source links useful outside GitHub, including images.
revision = review.revision if review is not None and review.page is not None else 'main'
text = source_links(text, args.repository, revision)
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
