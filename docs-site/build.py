"""Evaluate the Nix catalog and generate a Jekyll site and machine-readable exports."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from content import audit, render, source_links


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
    index = ['---\nlayout: default\n---\n', '# Purifier reference',
             'Generated from the typed behavior catalog. This initial catalog covers '
             'Ant and Docker; other purifier documentation still uses project READMEs.',
             '[Machine-readable catalog](catalog.json)']
    rows = ['| Fact | ' + ' | '.join(catalog) + ' |',
            '| --- | ' + ' | '.join('---' for _ in catalog) + ' |']
    for key in contract['facts']:
        cells = []
        for page in catalog.values():
            fact = page['facts'][key]
            if fact['state'] == 'known':
                value = fact['value']
                cell = ', '.join(value) if isinstance(value, list) else value
            else:
                cell = f'{fact["state"]}: {fact["reason"]}'
            cells.append(cell.replace('|', '&#124;').replace('\n', ' '))
        rows.append('| ' + key + ' | ' + ' | '.join(cells) + ' |')
    reports = {}
    for name, (markdown, variations) in rendered.items():
        page = catalog[name]
        target = destination / name
        target.mkdir(exist_ok=True)
        # Page-scoped title and repository allow the shared layout to work in
        # both a combined catalog and a project's independent Pages build.
        frontmatter = ('---\nlayout: default\ntitle: ' + json.dumps(name) +
                       '\nrepository: ' + json.dumps(page['repository']) + '\n---\n\n')
        (target / 'index.md').write_text(frontmatter + source_links(markdown, page['repository']))
        (target / 'system.json').write_text(json.dumps(page, indent=2) + '\n')
        reports[name] = audit(page, variations)
        index.append(f'- [{name}]({name}/)')
    index.extend(['## Comparison', '\n'.join(rows),
                  '[Variations and unresolved facts](content-variations.json)'])
    (destination / 'index.md').write_text('\n\n'.join(index) + '\n')
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
