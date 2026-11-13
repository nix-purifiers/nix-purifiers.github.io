"""Bind curated compatibility points to tested inputs; never infer new support."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from datetime import datetime, timedelta

from compatibility import EMPTY, validate


def relevant(path):
    # Native fixtures and build inputs can live under any name or directory.
    return True


# Public GitHub-hosted runner labels, reviewed against GitHub's runner reference:
# https://docs.github.com/en/actions/reference/runners/github-hosted-runners
RUNNER_SYSTEMS = {'ubuntu-latest': 'x86_64-linux', 'ubuntu-24.04': 'x86_64-linux',
                  'ubuntu-24.04-arm': 'aarch64-linux', 'macos-latest': 'aarch64-darwin',
                  'macos-15': 'aarch64-darwin'}


def runner_system(labels):
    if not labels or any(label not in RUNNER_SYSTEMS for label in labels):
        raise ValueError('unknown runner labels; platform evidence requires review')
    systems = {RUNNER_SYSTEMS[label] for label in labels}
    if len(systems) != 1: raise ValueError('ambiguous runner platform evidence')
    return systems.pop()


def git(checkout, *args):
    return subprocess.check_output(['git', '-C', str(checkout), *args])


def inputs(checkout, revision):
    """Hash tracked source, fixtures, SDK definitions and native check workflows."""
    files = {}
    entries = git(checkout, 'ls-tree', '-rz', revision).split(b'\0')
    selected = []
    for entry in entries:
        if not entry: continue
        metadata, path = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        path = path.decode()
        if relevant(path): selected.append((path, mode, kind, oid))
    # cat-file avoids one subprocess per input, including binary fixtures.
    objects = [oid for _, _, kind, oid in selected if kind == 'blob']
    payload = subprocess.check_output(['git', '-C', str(checkout), 'cat-file', '--batch'],
                                      input=('\n'.join(objects)+'\n').encode()) if objects else b''
    position = 0
    for path, mode, kind, oid in selected:
        if kind == 'commit':
            data = ('gitlink:'+oid).encode()
        elif kind == 'blob':
            end = payload.index(b'\n', position)
            header = payload[position:end].split()
            if len(header) != 3 or header[1] != b'blob': raise ValueError(f'{path}: missing Git object')
            size = int(header[2]); position = end+1
            data = payload[position:position+size]; position += size+1
            if mode == '120000': data = b'symlink:'+data
        else: raise ValueError(f'{path}: unexpected Git object type {kind}')
        # Executability and symlink/gitlink modes are part of behavior too.
        files[path] = hashlib.sha256(mode.encode()+b'\0'+data).hexdigest()
    return dict(sorted(files.items()))


def input_digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


PINNED_PUBLICATION_POLICY = '1f49d62ee4b263cf8a9d09a1921faebd1d536fc3'
PINNED_PUBLICATION_SCRIPT_SHA256 = 'f87788f6ab5cb60a95dca46abad1b11a00f11827fb14ec48240a7a5d6d97fb42'
PINNED_NOOP_MESSAGE = 'The latest release already contains these sources and locked dependencies.'


def publication_inputs_1f49(files):
    """Historical policy: deliberately independent of later publisher exceptions."""
    return {p: h for p, h in files.items()
            if not p.startswith(('tests/', 'docs/', '.github/'))
            and p not in ('README.md', '.gitignore')}


def retained_publication_asset(url, directory, extension='json'):
    prefix = 'https://nix-purifiers.github.io/evidence/'
    match = re.fullmatch(re.escape(prefix) + r'([0-9a-f]{64})\.' + extension, url) if isinstance(url, str) else None
    if not match:
        raise ValueError('runtime publication requires retained content-addressed evidence')
    try:
        raw = (Path(directory) / url[len(prefix):]).read_bytes()
    except OSError as error:
        raise ValueError('runtime publication evidence is missing') from error
    if hashlib.sha256(raw).hexdigest() != match[1]:
        raise ValueError('runtime publication evidence hash differs')
    return raw


def publication_archive_fingerprint(raw, reviewed_files, repository):
    """Reconstruct Git identities from retained bodies, never from supplied IDs."""
    def require(value, message):
        if not value:
            raise ValueError('runtime publication: ' + message)
    prefix = repository.rsplit('/', 1)[-1]
    expected_directories = {prefix}
    for path in reviewed_files:
        expected_directories.update(prefix + '/' + str(parent)
                                    for parent in PurePosixPath(path).parents if str(parent) != '.')
    directories = set()
    inventory = {}
    git_entries = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r|gz') as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                require(not path.is_absolute() and '..' not in path.parts
                        and bool(path.parts) and path.parts[0] == prefix
                        and member.name.rstrip('/') == path.as_posix(), 'unsafe released archive path')
                name = path.as_posix()
                if member.isdir():
                    require(name in expected_directories and name not in directories,
                            'unexpected or duplicate released archive directory')
                    directories.add(name)
                    continue
                require(len(path.parts) > 1 and member.name == name, 'invalid released archive file')
                relative = PurePosixPath(*path.parts[1:]).as_posix()
                require(relative in reviewed_files and relative not in inventory,
                        'unexpected or duplicate released archive file')
                if member.issym():
                    mode = '120000'
                    body = member.linkname.encode('utf-8', 'surrogateescape')
                    digest = hashlib.sha256(mode.encode() + b'\0symlink:' + body).hexdigest()
                    blob = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
                else:
                    require(member.type in (tarfile.REGTYPE, tarfile.AREGTYPE),
                            'unsupported released archive file type')
                    mode = '100755' if member.mode & 0o111 else '100644'
                    digest_hash = hashlib.sha256(mode.encode() + b'\0')
                    blob_hash = hashlib.sha1(b'blob ' + str(member.size).encode() + b'\0')
                    stream = archive.extractfile(member)
                    size = 0
                    while chunk := stream.read(65536):
                        digest_hash.update(chunk)
                        blob_hash.update(chunk)
                        size += len(chunk)
                    require(size == member.size, 'truncated released archive file')
                    digest, blob = digest_hash.hexdigest(), blob_hash.hexdigest()
                inventory[relative] = digest
                git_entries[relative] = mode + ' blob ' + blob + '\t' + relative
    except (tarfile.TarError, OSError, EOFError) as error:
        raise ValueError('runtime publication: invalid released source archive') from error
    require(inventory == reviewed_files and directories == expected_directories,
            'released archive differs from the complete reviewed runtime inventory')
    eligible = publication_inputs_1f49(reviewed_files)
    rows = [git_entries[path].encode('utf-8') for path in sorted(eligible, key=lambda p: p.encode('utf-8'))]
    return hashlib.sha256(b'\0'.join(rows)).hexdigest()


def validate_runtime_publication(point, entry, repository, directory):
    """Bind a fixture-only check to an unchanged, already published runtime."""
    publication = point['runtimePublication']
    def require(value, message):
        if not value:
            raise ValueError('runtime publication: ' + message)
    def asset(url, extension='json'):
        return retained_publication_asset(url, directory, extension)
    def record(url):
        raw = asset(url)
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise ValueError('runtime publication: invalid retained JSON') from error
    proof = record(publication['proof'])
    fields = {'version', 'repository', 'testedSourceRevision', 'runtimeSourceRevision',
              'releasedVersion', 'publication', 'newSourceArchivePublished',
              'policyRevision', 'policySource', 'testedInputDigest', 'runtimeInputDigest',
              'equivalentInputs', 'runtimeFingerprint', 'releaseManifest', 'runtimeArchive',
              'releaseChecksums', 'publicationRun', 'publicationJobs',
              'publicationLog'}
    require(isinstance(proof, dict) and set(proof) == fields, 'invalid proof fields')
    require(type(proof['version']) is int and proof['version'] == 1
            and proof['repository'] == repository, 'wrong proof identity')
    require(proof['testedSourceRevision'] == point['sourceRevision']
            and proof['runtimeSourceRevision'] == publication['sourceRevision']
            and proof['releasedVersion'] == publication['version'], 'wrong source or release binding')
    require(proof['testedSourceRevision'] != proof['runtimeSourceRevision'], 'sources must be distinct')
    require(proof['publication'] == 'noop' and proof['newSourceArchivePublished'] is False,
            'requires an unchanged runtime and no new tested-source archive')
    require(proof['policyRevision'] == PINNED_PUBLICATION_POLICY, 'unknown publisher policy')
    require(hashlib.sha256(asset(proof['policySource'], 'txt')).hexdigest()
            == PINNED_PUBLICATION_SCRIPT_SHA256, 'wrong pinned publisher script')
    def inventory(revision):
        matches = [r for r in entry['reviews'] if r['sourceRevision'] == revision]
        require(bool(matches), 'source inventory is not reviewed')
        require(all(r['files'] == matches[0]['files'] for r in matches), 'ambiguous source inventory')
        require(isinstance(matches[0]['files'], dict), 'invalid source inventory')
        return matches[0]['files']
    tested = inventory(point['sourceRevision'])
    runtime = inventory(publication['sourceRevision'])
    require(proof['testedInputDigest'] == input_digest(tested)
            and proof['runtimeInputDigest'] == input_digest(runtime), 'wrong full source inventory digest')
    selected_tested = publication_inputs_1f49(tested)
    selected_runtime = publication_inputs_1f49(runtime)
    require(bool(selected_tested) and selected_tested == selected_runtime
            and proof['equivalentInputs'] == selected_runtime,
            'complete publisher input sets and mode-aware hashes must match')
    manifest = record(proof['releaseManifest'])
    require(isinstance(manifest, dict) and manifest.get('kind') == 'source'
            and manifest.get('commit') == publication['sourceRevision']
            and manifest.get('version') == publication['version']
            and isinstance(proof['runtimeFingerprint'], str)
            and re.fullmatch('[0-9a-f]{64}', proof['runtimeFingerprint'])
            and manifest.get('fingerprint') == proof['runtimeFingerprint'], 'wrong released manifest')
    try:
        sums = asset(proof['releaseChecksums'], 'txt').decode('ascii').splitlines()
    except UnicodeError as error:
        raise ValueError('runtime publication: invalid released checksums') from error
    matches = [re.fullmatch(r'([0-9a-f]{64})  (release-manifest\.json|source\.tar\.gz)', line)
               for line in sums]
    require(len(matches) == 2 and all(matches), 'invalid released checksum entries')
    checksums = {match[2]: match[1] for match in matches}
    require(set(checksums) == {'release-manifest.json', 'source.tar.gz'}, 'missing released checksums')
    archive = asset(proof['runtimeArchive'], 'bin')
    require(checksums['source.tar.gz'] == hashlib.sha256(archive).hexdigest()
            and checksums['release-manifest.json'] == hashlib.sha256(asset(proof['releaseManifest'])).hexdigest(),
            'released archive or manifest checksum differs')
    expected_fingerprint = publication_archive_fingerprint(archive, runtime, repository)
    require(expected_fingerprint == proof['runtimeFingerprint'] == manifest['fingerprint'],
            'recomputed runtime fingerprint differs')
    run = record(proof['publicationRun'])
    require(isinstance(run, dict) and run.get('head_sha') == point['sourceRevision']
            and type(run.get('id')) is int and run['id'] > 0
            and run.get('head_branch') == 'main' and run.get('status') == 'completed'
            and run.get('conclusion') == 'success'
            and isinstance(run.get('repository'), dict)
            and run['repository'].get('full_name') == repository, 'wrong publisher run')
    workflow = ('nix-purifiers/nix-purifiers.github.io/.github/workflows/purifier-release.yml@'
                + PINNED_PUBLICATION_POLICY)
    require(isinstance(run.get('referenced_workflows'), list)
            and any(isinstance(w, dict) and w.get('path') == workflow
                and w.get('sha') == PINNED_PUBLICATION_POLICY
                for w in run.get('referenced_workflows', [])), 'publisher workflow is not the pinned policy')
    jobs = record(proof['publicationJobs'])
    require(isinstance(jobs, dict) and jobs.get('total_count') == 1
            and isinstance(jobs.get('jobs'), list)
            and len(jobs.get('jobs', [])) == 1, 'requires the exact publisher job')
    job = jobs['jobs'][0]
    require(isinstance(job, dict) and job.get('run_id') == run.get('id')
            and job.get('head_sha') == point['sourceRevision']
            and job.get('status') == 'completed' and job.get('conclusion') == 'success',
            'wrong publisher job source or result')
    require(isinstance(job.get('steps'), list) and all(isinstance(s, dict) for s in job['steps']),
            'invalid publisher steps')
    steps = [s for s in job.get('steps', []) if s.get('number') == 5]
    require(len(steps) == 1 and steps[0].get('status') == 'completed'
            and steps[0].get('conclusion') == 'success'
            and steps[0].get('name') == 'Release checked sources and native integrations',
            'publisher step did not execute successfully')
    try:
        start = datetime.fromisoformat(steps[0]['started_at'])
        end = datetime.fromisoformat(steps[0]['completed_at']) + timedelta(seconds=1)
        lines = asset(proof['publicationLog'], 'log').decode('utf-8').splitlines()
        observed = [datetime.fromisoformat(line.split(' ', 1)[0]) for line in lines
                    if line.endswith(PINNED_NOOP_MESSAGE)]
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise ValueError('runtime publication: invalid publisher execution log') from error
    require(start.tzinfo is not None and end.tzinfo is not None
            and all(time.tzinfo is not None for time in observed), 'publisher timestamps need time zones')
    require(any('[command]/usr/bin/git checkout --progress --force ' + PINNED_PUBLICATION_POLICY
                in line for line in lines)
            and any('##[group]Run python3 .release-infrastructure/release/publish.py' in line
                    for line in lines), 'pinned publisher checkout and invocation are missing')
    require(any(start <= time < end for time in observed), 'no executed NOOP in publisher step')


def validate_registry(registry, catalog):
    if set(registry) != {'version', 'projects'} or registry['version'] != 1:
        raise ValueError('unsupported compatibility evidence registry')
    for name, entry in registry['projects'].items():
        if name not in catalog or set(entry) != {'testedPoints', 'reviews'}:
            raise ValueError(f'{name}: unknown project or invalid evidence fields')
        data = dict(EMPTY, testedPoints=entry['testedPoints'])
        validate(data)
        if catalog[name]['compatibility']['testedPoints'] != entry['testedPoints']:
            raise ValueError(f'{name}: catalog tested points differ from reviewed registry')
        points = {p['id']: p for p in entry['testedPoints']}
        covered = set()
        repository = catalog[name]['repository']
        for review in entry['reviews']:
            if set(review) != {'sourceRevision', 'files', 'inputDigest', 'pointIds', 'ci'}:
                raise ValueError(f'{name}: invalid input review fields')
            if (not re.fullmatch('[0-9a-f]{40}', review['sourceRevision']) or not review['files']
                    or not review['pointIds'] or not review['ci']):
                raise ValueError(f'{name}: incomplete source/CI binding')
            for path, digest in review['files'].items():
                if (path.startswith('/') or '..' in Path(path).parts or not relevant(path)
                        or not re.fullmatch('[0-9a-f]{64}', digest)):
                    raise ValueError(f'{name}: invalid source input {path}')
            if review['inputDigest'] != input_digest(review['files']):
                raise ValueError(f'{name}: input digest does not match reviewed files')
            jobs = []
            for ci in review['ci']:
                if (set(ci) != {'runId', 'attempt', 'headRevision', 'inputDigest', 'jobs'}
                        or not isinstance(ci['runId'], int) or ci['runId'] <= 0
                        or not isinstance(ci['attempt'], int) or ci['attempt'] <= 0
                        or not re.fullmatch('[0-9a-f]{40}', ci['headRevision'])
                        or ci['inputDigest'] != review['inputDigest'] or not ci['jobs']):
                    raise ValueError(f'{name}: CI did not test the reviewed inputs')
                for job in ci['jobs']:
                    if (set(job) != {'id', 'name', 'system', 'conclusion'} or job['conclusion'] != 'success'
                            or not isinstance(job['id'], int) or job['id'] <= 0
                            or not job['name'].strip() or not job['system'].strip()):
                        raise ValueError(f'{name}: compatibility requires successful scoped jobs')
                    jobs.append((ci, job))
            for point_id in review['pointIds']:
                if point_id not in points or point_id in covered:
                    raise ValueError(f'{name}: unknown or repeated point binding {point_id}')
                point = points[point_id]
                if point['sourceRevision'] != review['sourceRevision']:
                    raise ValueError(f'{name}/{point_id}: wrong reviewed source')
                prefix = f'https://github.com/{repository}/blob/{review["sourceRevision"]}/'
                definitions = [url[len(prefix):] for url in point['evidence'] if url.startswith(prefix)]
                if not definitions or any(path not in review['files'] for path in definitions):
                    raise ValueError(f'{name}/{point_id}: test definition is not bound to reviewed inputs')
                matching = [(ci, job) for ci, job in jobs if job['system'] == point['system']]
                if not any(any(url == f'https://github.com/{repository}/actions/runs/{ci["runId"]}' or
                               url == f'https://github.com/{repository}/actions/runs/{ci["runId"]}/job/{job["id"]}'
                               for url in point['evidence']) for ci, job in matching):
                    raise ValueError(f'{name}/{point_id}: no matching successful platform/CI evidence')
                covered.add(point_id)
        if covered != set(points): raise ValueError(f'{name}: tested points lack reviewed inputs')
        for point in points.values():
            if 'runtimePublication' in point:
                validate_runtime_publication(point, entry, repository,
                                             Path(__file__).with_name('evidence'))
    for name, page in catalog.items():
        if page['compatibility']['testedPoints'] and name not in registry['projects']:
            raise ValueError(f'{name}: tested points exist outside the evidence registry')


def audit_source(checkout, review, revision='HEAD', clean=True):
    if clean and git(checkout, 'status', '--porcelain').strip():
        raise ValueError(f'{checkout}: uncommitted source; select a clean checkout')
    current = git(checkout, 'rev-parse', revision).decode().strip()
    observed = inputs(checkout, current)
    changed = sorted(path for path in set(observed) | set(review['files'])
                     if observed.get(path) != review['files'].get(path))
    return dict(status='review-needed' if changed else 'inputs-match', currentRevision=current,
                testedRevision=review['sourceRevision'], changedFiles=changed)


def verify_ci(repository, review, checkout, fetch=False):
    """Read actual GitHub job conclusions and verify the CI source fingerprint."""
    def api(path):
        return json.loads(subprocess.check_output(['gh', 'api', path], text=True))
    if fetch:
        subprocess.run(['git', '-C', str(checkout), 'fetch', '-q', 'origin', review['sourceRevision']], check=True)
    if inputs(checkout, review['sourceRevision']) != review['files']:
        raise ValueError(f'{repository}: recorded inputs differ from the claimed source revision')
    for evidence in review['ci']:
        run = api(f'repos/{repository}/actions/runs/{evidence["runId"]}')
        if run['head_sha'] != evidence['headRevision'] or run['run_attempt'] != evidence['attempt']:
            raise ValueError(f'{repository}: CI source or attempt changed; review again')
        if fetch:
            subprocess.run(['git', '-C', str(checkout), 'fetch', '-q', 'origin', run['head_sha']], check=True)
        if input_digest(inputs(checkout, run['head_sha'])) != review['inputDigest']:
            raise ValueError(f'{repository}: CI source inputs differ from the recorded test')
        for expected in evidence['jobs']:
            job = api(f'repos/{repository}/actions/jobs/{expected["id"]}')
            if (job['run_id'] != evidence['runId'] or job['head_sha'] != run['head_sha']
                    or job['name'] != expected['name'] or job['status'] != 'completed'
                    or job['conclusion'] != 'success'
                    or runner_system(job.get('labels')) != expected['system']):
                raise ValueError(f'{repository}: required CI job {expected["id"]} is not successful')
