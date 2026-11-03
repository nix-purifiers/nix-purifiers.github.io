"""Evaluate the Nix catalog and generate a Jekyll site and machine-readable exports."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from content import audit, feature_matrix, render, source_links
from theme import install_theme
from reference import reference_text


def build(documentation, destination):
    """Validate every record before writing any output files."""
    contract = documentation['contract']
    catalog = documentation['catalog']
    rendered = {}
    for name, page in catalog.items():
        if name != page['repository'].split('/')[1]:
            raise ValueError(f'{name}: catalog key must match repository name')
        rendered[name] = render(page, contract)
    theme = Path(__file__).parent
    install_theme(destination)
    (destination / '_config.yml').write_text(json.dumps({
        'title': 'Purifier reference', 'description': 'Structured purifier behavior catalog',
        'feature_matrices': {page['repository']: f'/{name}/features.html' for name, page in catalog.items()},
        'url': 'https://nix-purifiers.github.io', 'baseurl': '',
        'markdown': 'kramdown', 'kramdown': {'input': 'GFM'},
    }))
    (destination / 'catalog.json').write_text(json.dumps(documentation, indent=2) + '\n')
    # Preserve the user-facing family homepage, including projects whose
    # documentation is hosted independently. Audit data is exported separately.
    (destination / 'index.md').unlink(missing_ok=True)
    shutil.copyfile(theme.parent / 'index.html', destination / 'index.html')
    reports = {}
    for name, (markdown, variations) in rendered.items():
        page = catalog[name]
        target = destination / name
        target.mkdir(exist_ok=True)
        # Page-scoped title and repository allow the shared layout to work in
        # both a combined catalog and a project's independent Pages build.
        frontmatter = ('---\nlayout: default\ntitle: ' + json.dumps(name) +
                       '\nrepository: ' + json.dumps(page['repository']) +
                       '\n---\n\n')
        reference = theme / 'references' / (name + '.md')
        if reference.exists():
            frontmatter = frontmatter.replace('\n---\n', '\nreference: ' + json.dumps(f'/{name}/reference.html') + '\n---\n')
            (target / 'reference.md').write_text('---\nlayout: default\nrepository: ' +
                json.dumps(page['repository']) + '\n---\n\n' + source_links(reference_text(page['repository'], reference.read_text(), page), page['repository']))
        (target / 'index.md').write_text(frontmatter + source_links(markdown, page['repository']))
        matrix_frontmatter = ('---\nlayout: default\ntitle: ' + json.dumps(name + ' feature matrix') +
                              '\nrepository: ' + json.dumps(page['repository']) + '\n---\n\n')
        (target / 'features.md').write_text(matrix_frontmatter + feature_matrix(page, contract))
        (target / 'system.json').write_text(json.dumps(page, indent=2) + '\n')
        reports[name] = audit(page, variations)
    (destination / 'content-variations.json').write_text(json.dumps(reports, indent=2) + '\n')
    library = theme / 'references/purifier.md'
    if library.exists():
        (destination / 'purifier').mkdir(exist_ok=True)
        (destination / 'purifier/index.md').write_text('---\nlayout: default\nrepository: nix-purifiers/purifier\n---\n\n' +
            source_links(reference_text('nix-purifiers/purifier', library.read_text()), 'nix-purifiers/purifier'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.catalog-source'))
    parser.add_argument('--export', type=Path, help='Use an already evaluated documentation JSON export')
    args = parser.parse_args()
    if args.export:
        documentation = json.loads(args.export.read_text())
    else:
        result = subprocess.run(
            ['nix', 'eval', '--json', '.#documentation'],
            cwd=Path(__file__).resolve().parent.parent, check=True,
            capture_output=True, text=True)
        documentation = json.loads(result.stdout)
    build(documentation, args.output)
