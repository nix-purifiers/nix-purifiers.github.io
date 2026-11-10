"""Evaluate the Nix catalog and generate a Jekyll site and machine-readable exports."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from content import audit, feature_matrix, render_overview, source_links
from theme import install_theme
from reference import guide_plan, reference_text
from testing import build_testing
from quality import registry, render_tiers, homepage
from authority import project_root, canonicalize, entry, validate_inputs


def build(documentation, destination):
    """Validate every record before writing any output files."""
    validate_inputs(documentation)
    contract = documentation['contract']
    catalog = documentation['catalog']
    rendered = {}
    guides = {}
    for name, page in catalog.items():
        if name != page['repository'].split('/')[1]:
            raise ValueError(f'{name}: catalog key must match repository name')
        text = (Path(__file__).parent / 'references' / (name + '.md')).read_text()
        guides[name] = (guide_plan(page['repository'], text), reference_text(page['repository'], text, page))
        rendered[name] = render_overview(page, contract, guides[name][0])
    theme = Path(__file__).parent
    quality = registry()
    install_theme(destination, quality)
    shutil.copytree(theme / 'evidence', destination / 'evidence', dirs_exist_ok=True)
    (destination / 'tiers.md').write_text('---\nlayout: default\ntitle: Purifier tiers\n---\n\n' + canonicalize(render_tiers(quality), catalog))
    (destination / '_config.yml').write_text(json.dumps({
        'title': 'Purifier reference', 'description': 'Structured purifier behavior catalog',
        'feature_matrices': {page['repository']: project_root(page['repository']) + 'features.html' for name, page in catalog.items()},
        'documentation_roots': {page['repository']: project_root(page['repository']) for page in catalog.values()},
        'central_documentation': True,
        'url': 'https://nix-purifiers.github.io', 'baseurl': '',
        'markdown': 'kramdown', 'kramdown': {'input': 'GFM'},
    }))
    (destination / 'catalog.json').write_text(json.dumps(documentation, indent=2) + '\n')
    # Preserve the user-facing family homepage, including projects whose
    # documentation is hosted independently. Audit data is exported separately.
    (destination / 'index.md').unlink(missing_ok=True)
    names = [*catalog, 'purifier']
    (destination / 'index.html').write_text(canonicalize(homepage((theme.parent / 'index.html').read_text(), quality), names))
    (destination / 'projects').mkdir(exist_ok=True)
    reports = {}
    for name, (markdown, variations) in rendered.items():
        page = catalog[name]
        target = destination / 'projects' / name
        target.mkdir(exist_ok=True)
        # Page-scoped title and repository allow the shared layout to work in
        # both a combined catalog and a project's independent Pages build.
        frontmatter = ('---\nlayout: default\ntitle: ' + json.dumps(name) +
                       '\nrepository: ' + json.dumps(page['repository']) +
                       '\n---\n\n')
        reference = theme / 'references' / (name + '.md')
        if reference.exists():
            (target / 'guide-structure.json').write_text(json.dumps(guides[name][0], indent=2) + '\n')
            (target / 'reference.md').write_text('---\nlayout: default\nrepository: ' +
                json.dumps(page['repository']) + '\n---\n\n' + source_links(guides[name][1], page['repository']))
        (target / 'index.md').write_text(frontmatter + source_links(markdown, page['repository']))
        matrix_frontmatter = ('---\nlayout: default\ntitle: ' + json.dumps(name + ' feature matrix') +
                              '\nrepository: ' + json.dumps(page['repository']) + '\n---\n\n')
        (target / 'features.md').write_text(matrix_frontmatter + feature_matrix(page, contract))
        (target / 'system.json').write_text(json.dumps(page, indent=2) + '\n')
        for filename in ('index.md', 'reference.md', 'features.md'):
            path = target / filename
            path.write_text(canonicalize(path.read_text(), names))
        legacy = destination / name
        legacy.mkdir(exist_ok=True)
        # Preserve machine-readable legacy URLs as explicitly revision-bound
        # snapshots. Current human documentation lives only under /projects/.
        (legacy / 'system.json').write_bytes((target / 'system.json').read_bytes())
        (legacy / 'guide-structure.json').write_bytes((target / 'guide-structure.json').read_bytes())
        for filename in ('index.html', 'reference.html', 'features.html'):
            (legacy / filename.replace('.html', '.md')).write_text(entry(page['repository'], filename, reference=guides[name][1] if filename == 'reference.html' else None))
        reports[name] = audit(page, variations)
    (destination / 'content-variations.json').write_text(json.dumps(reports, indent=2) + '\n')
    library = theme / 'references/purifier.md'
    if library.exists():
        (destination / 'projects/purifier').mkdir(exist_ok=True)
        (destination / 'projects/purifier/index.md').write_text('---\nlayout: default\nrepository: nix-purifiers/purifier\n---\n\n' +
            canonicalize(source_links(reference_text('nix-purifiers/purifier', library.read_text()), 'nix-purifiers/purifier'), names))
        (destination / 'purifier').mkdir(exist_ok=True)
        (destination / 'purifier/index.md').write_text(entry('nix-purifiers/purifier'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.catalog-source'))
    parser.add_argument('--export', type=Path, help='Use an already evaluated documentation JSON export')
    parser.add_argument('--coverage-plan', type=Path, help='Coverage obligations exported from .#coveragePlan')
    parser.add_argument('--coverage-audit', type=Path, help='Context-bound audit from harness/coverage.py')
    args = parser.parse_args()
    if args.coverage_audit and not args.coverage_plan:
        parser.error('--coverage-audit requires --coverage-plan')
    if args.export:
        documentation = json.loads(args.export.read_text())
    else:
        result = subprocess.run(
            ['nix', 'eval', '--json', '.#documentation'],
            cwd=Path(__file__).resolve().parent.parent, check=True,
            capture_output=True, text=True)
        documentation = json.loads(result.stdout)
    build(documentation, args.output)
    plan = json.loads(args.coverage_plan.read_text()) if args.coverage_plan else None
    if plan is None and not args.export:
        result = subprocess.run(['nix', 'eval', '--json', '.#coveragePlan'],
                                cwd=Path(__file__).resolve().parent.parent, check=True,
                                capture_output=True, text=True)
        plan = json.loads(result.stdout)
    if plan is not None:
        audit = json.loads(args.coverage_audit.read_text()) if args.coverage_audit else None
        build_testing(plan, audit, args.output)
