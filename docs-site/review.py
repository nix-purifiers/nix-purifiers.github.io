"""Verify that generated documentation still describes its reviewed source."""
import argparse
import hashlib
import json
from pathlib import Path


def excluded(relative, repository):
    if relative.startswith(('docs/', '.git/')) or relative in {
        'LICENSE', 'LICENSE.md', 'COPYING', '.gitignore', '.gitattributes',
    }:
        return True
    if relative == '.github/workflows/pages.yml':
        return True
    return repository == 'nix-purifiers/sbt-purifier' and relative == '.github/workflows/release.yml'


def verify(repository, checkout, manifest=None):
    """Reject changed or missing reviewed files, ignoring workflow-only changes."""
    if manifest is None:
        manifest = json.loads((Path(__file__).parent.parent / 'model/repositories.json').read_text())
    name = repository.split('/')[1]
    if name not in manifest or manifest[name]['repository'] != repository:
        raise ValueError(f'no source review recorded for {repository}')
    record = manifest[name]
    def digest(path):
        payload = ('symlink:' + str(path.readlink())).encode() if path.is_symlink() else path.read_bytes()
        return hashlib.sha256(payload).hexdigest()
    changed = []
    for relative, expected in record['files'].items():
        path = checkout / relative
        if not (path.is_file() or path.is_symlink()) or digest(path) != expected:
            changed.append(relative)
    # New implementation files matter too. Exclude deployment and developer
    # notes just as in the reviewed manifest; those do not change the tool.
    import subprocess
    tracked = subprocess.run(['git', '-C', str(checkout), 'ls-files', '-z'],
                             check=True, capture_output=True).stdout.decode().split('\0')
    for relative in tracked:
        if not relative or excluded(relative, repository):
            continue
        if relative not in record['files']:
            changed.append(relative)
    if changed:
        raise ValueError(f'{repository}: documentation model needs source review; changed since '
                         f'{record["revision"][:12]}: {", ".join(sorted(set(changed)))}')
    return record['revision']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository')
    parser.add_argument('--checkout', type=Path)
    parser.add_argument('--checkouts', type=Path, help='Directory containing all reviewed repositories')
    args = parser.parse_args()
    if args.checkouts:
        manifest = json.loads((Path(__file__).parent.parent / 'model/repositories.json').read_text())
        for record in manifest.values():
            verify(record['repository'], args.checkouts / record['repository'].split('/')[1], manifest)
        print(f'Verified {len(manifest)} reviewed source trees.')
    elif args.repository and args.checkout:
        print(verify(args.repository, args.checkout))
    else:
        parser.error('use --repository and --checkout, or --checkouts')
