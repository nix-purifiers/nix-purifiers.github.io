"""Prepare a purifier README for its GitHub Pages documentation site."""
import argparse
import json
from pathlib import Path
import re
from content import audit, feature_matrix, render, render_overview, source_links
from theme import install_theme
from review import canonical_review, resolve_review, SourceDrift
from reference import guide_plan, reference_text
from export import validate_version_coverage
from quality import for_repository
from authority import project_root, entry

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repository', required=True)
parser.add_argument('--readme', default='README.md', type=Path)
parser.add_argument('--output', default='.pages-source', type=Path)
parser.add_argument('--content', type=Path,
                    help='Structured project JSON (defaults to docs-site/page.json beside README)')
parser.add_argument('--catalog', type=Path,
                    help='Nix documentation export containing catalog and contract')
parser.add_argument('--model', action='store_true', help='Use the bundled, validated model export')
source_options = parser.add_mutually_exclusive_group()
source_options.add_argument('--check-source', type=Path, help='Strict maintainer audit: reject native source drift')
source_options.add_argument('--source-status', type=Path,
                            help='Build bundled reviewed documentation and report native source drift')
args = parser.parse_args()
if not re.fullmatch(r'[\w.-]+/[\w.-]+', args.repository):
    parser.error('repository must be owner/name')
theme = Path(__file__).parent
review = None
source_status = None
if args.source_status:
    if not args.model or args.catalog or args.content:
        parser.error('--source-status requires --model without --catalog or --content')
    try:
        review = resolve_review(args.repository, args.source_status)
        if review.page is None and review.library is None:
            review = canonical_review(args.repository)
        source_status = {'repository': args.repository, 'status': 'matched',
                         'documentedRevision': review.revision, 'changedFiles': []}
        if review.page is not None:
            # An older complete review may lack newly required metadata, but
            # malformed reviewed content must still fail rather than fall back.
            render(review.page, json.loads((theme / 'catalog.json').read_text())['contract'])
            try:
                validate_version_coverage({args.repository: review.page})
            except (KeyError, ValueError):
                review = canonical_review(args.repository)
                source_status.update(status='update-needed', documentedRevision=review.revision,
                                     documentationReview=['packaged-version-metadata'])
    except SourceDrift as error:
        try:
            review = canonical_review(args.repository)
        except (ValueError, KeyError, OSError) as invalid:
            parser.error(str(invalid))
        source_status = {'repository': args.repository, 'status': 'update-needed',
                         'documentedRevision': review.revision, 'changedFiles': error.changed}
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
if args.check_source:
    try:
        review = resolve_review(args.repository, args.check_source)
    except ValueError as error:
        parser.error(str(error))
if review is not None and (review.page is not None or review.library is not None) and not args.model:
    parser.error('reviewed source variants require --model')
if args.model and args.repository != 'nix-purifiers/purifier':
    args.catalog = args.catalog or theme / 'catalog.json'
content_path = args.content or args.readme.parent / 'docs-site' / 'page.json'
content_exists = content_path.exists() and not args.source_status
if review is not None and review.library is not None and (args.catalog or args.content is not None or content_exists):
    parser.error('reviewed library variants use library.json, not tool page content')
differences = None
if args.catalog or args.content is not None or content_exists:
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
    # Quality reviews are orthogonal to native source snapshots. An older
    # reviewed page must not restore stale quality in system.json while its
    # shared layout displays the current central assessment.
    page = dict(page, quality=for_repository(args.repository))
    try:
        text, differences = render(page, contract)
    except ValueError as error:
        parser.error(str(error))
else:
    text = review.reference if review is not None and review.library is not None else args.readme.read_text()
    if args.repository == 'nix-purifiers/purifier':
        text = reference_text(args.repository, text, library=review.library if review is not None else None)
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
        resolved_plan = guide_plan(args.repository, guide, plan)
        text, _ = render_overview(page, contract, resolved_plan)
        (source / 'guide-structure.json').write_text(json.dumps(resolved_plan, indent=2) + '\n')
        (source / 'reference.md').write_text('---\nlayout: default\n---\n\n' + source_links(reference_text(args.repository, guide, page, plan), args.repository, revision))
else:
    for filename in ('content-variations.json', 'system.json', 'features.md', 'reference.md', 'guide-structure.json'):
        (source / filename).unlink(missing_ok=True)
# Keep source links useful outside GitHub, including images.
revision = review.revision if review is not None and (review.page is not None or review.library is not None) else 'main'
text = source_links(text, args.repository, revision)
if review is not None and review.library is not None:
    (source / 'library.json').write_text(json.dumps(review.library, indent=2) + '\n')
else:
    (source / 'library.json').unlink(missing_ok=True)
(source / 'index.md').write_text('---\nlayout: default\n---\n\n' + text)
if source_status is not None:
    (source / 'source-review.json').write_text(json.dumps(source_status, indent=2) + '\n')
    print(f'Documentation source: {source_status["status"]}; '
          f'documented revision {source_status["documentedRevision"]}')
else:
    (source / 'source-review.json').unlink(missing_ok=True)
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

# Compatibility entry points only: producer snapshots are never current docs.
# Keep validation and machine snapshots above, and preserve native payloads.
for filename in ('index.html', 'reference.html', 'features.html'):
    if filename != 'index.html' and differences is None:
        continue
    snapshot = 'system.json' if differences is not None else 'library.json' if review is not None and review.library is not None else None
    guide_text = guide if differences is not None and filename == 'reference.html' else None
    (source / filename.replace('.html', '.md')).write_text(entry(args.repository, filename, snapshot, guide_text))
config = json.loads((source / '_config.yml').read_text())
if differences is not None:
    root = 'https://nix-purifiers.github.io' + project_root(args.repository)
    config['feature_matrices'] = {args.repository: root + 'features.html'}
    config['documentation_roots'] = {args.repository: root}
config['central_documentation'] = False
(source / '_config.yml').write_text(json.dumps(config))
