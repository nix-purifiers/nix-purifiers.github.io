"""Export the validated Nix documentation model for Python-only Pages builders."""
import argparse
import json
from pathlib import Path
import subprocess
from reference import guide_plan
from inventory import validate_coverage


def validate_version_coverage(catalog):
    for name, page in catalog.items():
        versions = page['compatibility']
        if not versions['defaults'] or not any(item['role'] == 'native-tool' for item in versions['defaults'] + versions['projectSelections']):
            raise ValueError(f'{name}: record packaged versions and the actual native-tool version selection before publishing')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(['nix', 'eval', '--json', '.#documentation'], cwd=root,
                            check=True, capture_output=True, text=True)
    documentation = json.loads(result.stdout)
    manifest = json.loads((root / 'model/repositories.json').read_text())
    expected = set(manifest) - {'purifier'}
    if set(documentation['catalog']) != expected:
        raise SystemExit('Every purifier repository must have a modeled documentation page.')
    validate_version_coverage(documentation['catalog'])
    for name, page in documentation['catalog'].items():
        if page.get('reviewedRevision') != manifest[name]['revision']:
            raise SystemExit(f'{name}: model and source review revisions differ')
        guide_plan(page['repository'], (root / 'docs-site/references' / (name + '.md')).read_text())
    validate_coverage(documentation['catalog'], (root / 'index.html').read_text())
    target = root / 'docs-site/catalog.json'
    if args.check:
        if not target.exists() or json.loads(target.read_text()) != documentation:
            raise SystemExit('Documentation export is stale; run python3 docs-site/export.py')
    else:
        target.write_text(json.dumps(documentation, indent=2) + '\n')
