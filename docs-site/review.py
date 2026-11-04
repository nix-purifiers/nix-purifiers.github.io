"""Verify that generated documentation still describes its reviewed source."""
import argparse
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ReviewedSource:
    revision: str
    page: dict | None = None
    reference: str | None = None
    guide_plan: dict | None = None
    library: dict | None = None


class SourceDrift(ValueError):
    """Native source differs; the bundled documentation is still buildable."""

    def __init__(self, repository, revision, changed):
        self.revision = revision
        self.changed = changed
        super().__init__(f'{repository}: documentation model needs source review; changed since '
                         f'{revision[:12]}: {", ".join(changed)}')


def canonical_review(repository):
    """Load a coherent bundled model and guide, independent of native HEAD."""
    theme = Path(__file__).parent
    name = repository.split('/')[1]
    manifest = json.loads((theme.parent / 'model/repositories.json').read_text())
    record = manifest[name]
    if record['repository'] != repository:
        raise ValueError('canonical repository does not match source review')
    revision = record['revision']
    guide = (theme / 'references' / (name + '.md')).read_text()
    if repository == 'nix-purifiers/purifier':
        library = validate_library(json.loads((theme.parent / 'model/library.json').read_text()),
                                   repository, revision)
        if hashlib.sha256(guide.encode()).hexdigest() != record['files'].get('README.md'):
            raise ValueError('canonical library reference must match the reviewed README.md')
        return ReviewedSource(revision, reference=guide, library=library)
    page = json.loads((theme / 'catalog.json').read_text())['catalog'][name]
    if page['repository'] != repository or page['reviewedRevision'] != revision:
        raise ValueError('canonical page repository and revision must match source review')
    from reference import guide_plan
    guide_plan(repository, guide)
    return ReviewedSource(revision, page=page, reference=guide)


def validate_library(data, repository, revision):
    """Library scope is independent of the native-tool page contract."""
    if (set(data) != {'repository', 'reviewedRevision', 'platforms', 'limitations', 'validation'}
            or data['repository'] != repository or data['reviewedRevision'] != revision):
        raise ValueError('variant library repository and reviewedRevision must match its source review')
    for key in ('platforms', 'limitations', 'validation'):
        if (not isinstance(data[key], list)
                or any(not isinstance(item, str) or not item.strip() for item in data[key])
                or (key == 'platforms' and not data[key])):
            raise ValueError(f'variant library {key}: expected a list of nonempty strings')
    return data


def resolve_review(repository, checkout, manifest=None, variants=None):
    """Select exact reviewed source and its paired model; never infer capabilities."""
    if manifest is None:
        manifest = json.loads((Path(__file__).parent.parent / 'model/repositories.json').read_text())
    name = repository.split('/')[1]
    if name not in manifest or manifest[name]['repository'] != repository:
        raise ValueError(f'no source review recorded for {repository}')
    record = manifest[name]
    def digest(path):
        payload = ('symlink:' + str(path.readlink())).encode() if path.is_symlink() else path.read_bytes()
        return hashlib.sha256(payload).hexdigest()
    # New implementation files matter too. Exclude deployment and developer
    # notes just as in the reviewed manifest; those do not change the tool.
    import subprocess
    tracked = subprocess.run(['git', '-C', str(checkout), 'ls-files', '-z'],
                             check=True, capture_output=True).stdout.decode().split('\0')

    def changes(snapshot):
        changed = []
        for relative, expected in snapshot['files'].items():
            path = checkout / relative
            if not (path.is_file() or path.is_symlink()) or digest(path) != expected:
                changed.append(relative)
        for relative in tracked:
            if relative and not excluded(relative, repository) and relative not in snapshot['files']:
                changed.append(relative)
        return sorted(set(changed))

    changed = changes(record)
    if not changed:
        return ReviewedSource(record['revision'])
    if variants is None:
        variants = Path(__file__).parent / 'reviews'
    matches = []
    for source in sorted((Path(variants) / name).glob('*/source.json')):
        snapshot = json.loads(source.read_text())
        if snapshot.get('repository') != repository or changes(snapshot):
            continue
        matches.append((source, snapshot))
    if len(matches) > 1:
        raise ValueError(f'{repository}: multiple reviewed variants match this source')
    for source, snapshot in matches:
        if repository == 'nix-purifiers/purifier':
            model = source.parent / 'library.json'
            if not model.is_file():
                raise ValueError(f'{source}: reviewed library variant requires library.json')
            library = validate_library(json.loads(model.read_text()),
                                       repository, snapshot['revision'])
            guide = source.parent / 'reference.md'
            if not guide.is_file():
                raise ValueError(f'{source}: reviewed library variant requires reference.md')
            # The library retains its complete README rather than a tool guide plan.
            if hashlib.sha256(guide.read_bytes()).hexdigest() != snapshot['files'].get('README.md'):
                raise ValueError(f'{source}: library reference.md must match the reviewed README.md')
            return ReviewedSource(snapshot['revision'], reference=guide.read_text(), library=library)
        page = json.loads((source.parent / 'page.json').read_text())
        if page.get('repository') != repository or page.get('reviewedRevision') != snapshot['revision']:
            raise ValueError(f'{source}: variant page repository and reviewedRevision must match its source review')
        guide = source.parent / 'reference.md'
        if not guide.is_file():
            raise ValueError(f'{source}: reviewed variant requires reference.md')
        plan_file = source.parent / 'guide.json'
        plan = json.loads(plan_file.read_text()) if plan_file.exists() else None
        from reference import guide_plan
        guide_plan(repository, guide.read_text(), plan)
        return ReviewedSource(snapshot['revision'], page, guide.read_text(), plan)
    raise SourceDrift(repository, record['revision'], changed)


def verify(repository, checkout, manifest=None):
    """Reject unreviewed source, including changes outside a reviewed variant."""
    return resolve_review(repository, checkout, manifest).revision


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
