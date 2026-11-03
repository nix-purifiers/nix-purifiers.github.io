"""Evaluate the Nix catalog and generate a Jekyll site and machine-readable exports."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from content import audit, feature_matrix, render, source_links


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
    (destination / '_layouts').mkdir(parents=True, exist_ok=True)
    (destination / 'assets').mkdir(exist_ok=True)
    shutil.copyfile(theme / 'layout.html', destination / '_layouts/default.html')
    for asset in ('docs.css', 'docs.js'):
        shutil.copyfile(theme / asset, destination / 'assets' / asset)
    (destination / '_config.yml').write_text(json.dumps({
        'title': 'Purifier reference', 'description': 'Structured purifier behavior catalog',
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
                       '\nfeature_matrix: ' + json.dumps(f'/{name}/features.html') + '\n---\n\n')
        (target / 'index.md').write_text(frontmatter + source_links(markdown, page['repository']))
        matrix_frontmatter = ('---\nlayout: default\ntitle: ' + json.dumps(name + ' feature matrix') +
                              '\nrepository: ' + json.dumps(page['repository']) + '\n---\n\n')
        (target / 'features.md').write_text(matrix_frontmatter + feature_matrix(page, contract))
        (target / 'system.json').write_text(json.dumps(page, indent=2) + '\n')
        reports[name] = audit(page, variations)
    (destination / 'content-variations.json').write_text(json.dumps(reports, indent=2) + '\n')


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
