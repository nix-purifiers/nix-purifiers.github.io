"""Evaluate packaged versions from each purifier's own locked Nix definitions.

This records package selections, never runtime test results or supported ranges.
Bundled npm/PEAR metadata comes from the pinned host package with an explicit
cross-platform parent-version equality check; it does not assert target execution.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SELECTORS = json.loads((ROOT / 'model/toolchain-selectors.json').read_text())['projects']


def evaluate(checkout, name, system):
    components = []
    for item in SELECTORS[name]:
        value = item.get('valueExpression') or '(' + item['expression'] + '.version or null)'
        components.append('{ role=' + json.dumps(item['role']) + '; name=' + item.get('nameExpression', json.dumps(item['name'])) +
                          '; selection=' + json.dumps(item.get('selection', 'default')) + '; value=' + value + '; }')
    expression = ('let f=builtins.getFlake ' + json.dumps('path:' + str(checkout)) +
                  '; packageSet = system: import f.inputs.nixpkgs {inherit system;config.allowUnfree=true;overlays=[f.overlays.default];};'
                  'p=packageSet ' + json.dumps(system) + ';metadataPkgs=packageSet "x86_64-linux";s=p.' + json.dumps(name) +
                  ';in {systems=builtins.attrNames f.packages;components=[' + ' '.join(components) + '];}')
    result = subprocess.run(['nix', 'eval', '--impure', '--json', '--expr', expression],
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise ValueError(f'{name}/{system}: {result.stderr}')
    data = json.loads(result.stdout)
    if any(not isinstance(item['value'], str) or not item['value'].strip() for item in data['components']):
        raise ValueError(f'{name}/{system}: missing version; inspect the actual package binding')
    return data


def audit(name, checkouts):
    checkout = (checkouts / name).resolve()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True):
        raise ValueError(f'{name}: commit source changes before recording revision-bound versions')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
    host = evaluate(checkout, name, 'x86_64-linux')
    systems = host['systems']
    observed = {system: host if system == 'x86_64-linux' else evaluate(checkout, name, system) for system in systems}
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True):
        raise ValueError(f'{name}: source changed during version evaluation')
    assert revision == subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
    grouped = {}
    for system, result in observed.items():
        for item in result['components']:
            key = item['selection'], item['role'], item['name'], item['value']
            grouped.setdefault(key, []).append(system)
    definition = next((path for path in [
        'nix/cli.nix', f'pkgs/{name}/default.nix', 'pkgs/cli/default.nix', 'flake.nix',
    ] if (checkout / path).exists()))
    base = 'https://github.com/nix-purifiers/' + name + '/blob/' + revision + '/'
    defaults = [dict(selection=selection, role=role, name=component, version=version,
                     systems=sorted(platforms), sourceRevision=revision,
                     evidence=[base + 'flake.lock', base + definition])
                for (selection, role, component, version), platforms in grouped.items()]
    return dict(repository='nix-purifiers/' + name, revision=revision,
                lockDigest=hashlib.sha256((checkout / 'flake.lock').read_bytes()).hexdigest(),
                definitions={system: result['components'] for system, result in observed.items()}, defaults=defaults)


def write_json(path, data):
    payload = json.dumps(data, indent=2) + '\n'
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as temporary:
        temporary.write(payload)
        staged = Path(temporary.name)
    staged.chmod(0o644)
    staged.replace(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkouts', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--write', action='store_true', help='Update only compatibility.defaults in existing records')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'model/repositories.json').read_text())
    if set(SELECTORS) != set(manifest) - {'purifier'}:
        parser.error('Every native purifier needs reviewed toolchain selectors')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = dict(zip(SELECTORS, pool.map(lambda name: audit(name, args.checkouts), SELECTORS)))
    write_json(args.output, records)
    if args.write:
        target = ROOT / 'model/toolchain-defaults.json'
        write_json(target, {'version': 1, 'projects': {name: record['defaults'] for name, record in records.items()}})
    print(f'Recorded concrete packaged versions for {len(records)} purifiers.')
