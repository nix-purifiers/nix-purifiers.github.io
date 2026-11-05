"""Bind curated compatibility points to tested inputs; never infer new support."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from compatibility import EMPTY, validate


def relevant(path):
    # Native fixtures and build inputs can live under any name or directory.
    return True


# Public GitHub-hosted runner labels, reviewed against GitHub's runner reference:
# https://docs.github.com/en/actions/reference/runners/github-hosted-runners
RUNNER_SYSTEMS = {'ubuntu-latest': 'x86_64-linux', 'ubuntu-24.04': 'x86_64-linux',
                  'ubuntu-24.04-arm': 'aarch64-linux', 'macos-latest': 'aarch64-darwin'}


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
