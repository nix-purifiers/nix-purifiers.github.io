"""Unintegrated native CI execution variant; output NAR observation is optional.

Uses actual retained job/log captures. It checks their local content and bindings,
not their origin authenticity. Root still reviews captured evidence provenance.
This first variant handles the exact successful native `nix flake check -L` step.
Optional SDK/sample annotations are reviewed source/input bindings, not inferred
from dependency presence. Their provenance must be inspected in the original
review packet; string shape alone cannot prove runtime version or sample identity.
It does not alter the approved local-realization receipt schema.
"""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from derivation_evidence import digest, require, store, text, url
from receipt_artifacts import canonical_base, retain

RUNNERS = {'ubuntu-24.04-arm': 'aarch64-linux', 'ubuntu-24.04': 'x86_64-linux',
           'ubuntu-22.04': 'x86_64-linux', 'macos-14-arm64': 'aarch64-darwin',
           'macos-15-arm64': 'aarch64-darwin', 'macos-14': 'x86_64-darwin',
           'macos-15': 'x86_64-darwin', 'macos-26-arm64': 'aarch64-darwin'}


FORMATS = ('command-json', 'job-json', 'jobs-json', 'json', 'text')
COMMANDS = ('nix flake check -L', 'nix flake check --print-build-logs', 'nix flake check')


def retain_native_artifact(source, directory, public_base, format):
    require(format in FORMATS, 'explicit retained artifact format required')
    if format != 'text':
        return dict(retain(source, directory, public_base), format=format)
    raw = Path(source).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    target = Path(directory) / (digest + '.log')
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open('xb') as stream:
            stream.write(raw)
    except FileExistsError:
        require(not target.is_symlink() and target.read_bytes() == raw, 'unsafe retained log destination')
    return {'receipt': canonical_base(public_base) + target.name, 'artifactSha256': digest, 'format': format}


def read_native_artifact(directory, public_base, reference):
    require(isinstance(reference, dict) and set(reference) - {'format'} == {'receipt', 'artifactSha256'}, 'invalid retained native artifact')
    format = reference.get('format', 'command-json')
    require(format in FORMATS, 'unknown retained native artifact format')
    digest = reference['artifactSha256']
    require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest), 'retained artifact digest required')
    suffix = '.log' if format == 'text' else '.json'
    require(reference['receipt'] == canonical_base(public_base) + digest + suffix, 'canonical retained artifact URL mismatch')
    path = Path(directory) / (digest + suffix)
    require(not path.is_symlink(), 'retained artifacts must be regular files')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == digest, 'retained native artifact digest mismatch')
    return raw.decode() if format == 'text' else json.loads(raw)


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate_native_ci(e, artifact_directory, public_base):
    require(isinstance(e, dict) and set(e) - {'sdkVersions', 'sampleSources', 'sourceNarHash', 'stepName', 'logJobName', 'jobConclusion', 'runtimeAssertions'} == {'kind', 'repository', 'revision', 'system',
            'check', 'drvPath', 'predictedOutputs', 'observedOutputs', 'outputNarHashes',
            'jobUrl', 'jobArtifact', 'logArtifact', 'stepNumber', 'command', 'runnerImage'}, 'invalid native CI evidence')
    require(e.get('sourceNarHash') is None or digest(e['sourceNarHash']), 'invalid actual source NAR binding')
    require(e.get('stepName') is None or text(e['stepName']), 'invalid exact step name')
    require(e.get('logJobName') is None or text(e['logJobName']), 'invalid grouped-log job selector')
    sdks = e.get('sdkVersions', {})
    samples = e.get('sampleSources', [])
    require(isinstance(sdks, dict) and all(text(k) and text(v) for k, v in sdks.items()), 'invalid per-check SDK binding')
    require(isinstance(samples, list) and all(isinstance(s, dict) and set(s) == {'repository', 'revision', 'sourceNarHash'} and url(s['repository']) and isinstance(s['revision'], str) and re.fullmatch(r'[0-9a-f]{40}', s['revision']) and digest(s['sourceNarHash']) for s in samples), 'invalid sample input identity')
    require(e['kind'] == 'native-ci-execution', 'explicit execution variant required')
    require(isinstance(e['repository'], str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', e['repository']), 'exact source repository required')
    require(isinstance(e['revision'], str) and re.fullmatch(r'[0-9a-f]{40}', e['revision']), 'immutable source revision required')
    require(isinstance(e['system'], str) and re.fullmatch(r'(aarch64|x86_64)-(linux|darwin)', e['system']), 'native system required')
    scripted = isinstance(e['check'], dict)
    if not scripted:
        require(isinstance(e['check'], str) and e['check'].startswith('checks.' + e['system'] + '.') and re.fullmatch(r'checks\.[a-z0-9_-]+\.[a-zA-Z0-9_.-]+', e['check']), 'check must bind exact native system')
    else:
        check = e['check']
        require(set(check) - {'executionArtifact', 'reportArtifact', 'artifactMetadata', 'artifactName', 'buildArgv', 'transcriptLayout'} == {'kind', 'scriptPath', 'sourceUrl', 'scriptArtifact', 'lockArtifact', 'invoker', 'arguments', 'inputSourceHashes', 'replayNotes', 'assertionSnippet'}, 'script check requires executable replay bindings')
        require(check['kind'] == 'script-generated-derivation' and isinstance(check['scriptPath'], str) and re.fullmatch(r'[A-Za-z0-9_./-]+\.(py|sh)', check['scriptPath']) and '..' not in check['scriptPath'].split('/'), 'exact executable generator path required')
        require(check['sourceUrl'] == 'https://github.com/' + e['repository'] + '/blob/' + e['revision'] + '/' + check['scriptPath'], 'foreign generator source')
        require(e.get('sourceNarHash') is not None and sdks and text(check['replayNotes']), 'script derivation requires actual source/SDK/replay scope')
        require(isinstance(check['invoker'], str) and re.fullmatch(r'(nix shell [^;&|]+ -c )?(python3(?: -B)?|bash|sh)', check['invoker']) and isinstance(check['arguments'], str), 'exact logged generator invocation and arguments required')
        expected = check['invoker'] + ' ' + check['scriptPath'] + (' ' + check['arguments'] if check['arguments'] else '')
        require(e['command'] == expected and not any(token in expected for token in (';', '&&', '||', '\n')), 'logged script command mismatch')
        hashes = check['inputSourceHashes']
        require(isinstance(hashes, dict) and all(text(k) and isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for k, v in hashes.items()), 'actual generator input source hashes required')
        require(hashes.get(check['scriptPath']) == check['scriptArtifact'].get('artifactSha256') and hashes.get('flake.lock') == check['lockArtifact'].get('artifactSha256'), 'generator/lock artifact hashes must bind input source snapshot')
        generator = read_native_artifact(artifact_directory, public_base, check['scriptArtifact'])
        locked = read_native_artifact(artifact_directory, public_base, check['lockArtifact'])
        require(isinstance(generator, str) and text(generator) and isinstance(locked, dict) and locked.get('version') == 7 and isinstance(locked.get('nodes'), dict), 'retained executable generator and locked inputs required')
        require(text(check['assertionSnippet']) and check['assertionSnippet'] in generator, 'actual executable assertion source required')
    require(store(e['drvPath'], drv=True), 'exact derivation required')
    require(isinstance(e['predictedOutputs'], dict) and all(isinstance(k, str) and k.strip() and store(v) and not v.endswith('.drv') for k, v in e['predictedOutputs'].items()), 'invalid predicted output identity')
    require(isinstance(e['observedOutputs'], dict) and all(text(k) and store(v) and not v.endswith('.drv') for k, v in e['observedOutputs'].items()) and e['outputNarHashes'] is None, 'native output observations need identities; unrecorded hashes remain unknown')
    require(not e['observedOutputs'] or (scripted and e['check'].get('executionArtifact')), 'observed output paths require an actual archived build transcript')
    require(type(e['stepNumber']) is int and (scripted or e['command'] in COMMANDS), 'supported build command and exact step required')
    require(e['runnerImage'] in RUNNERS and RUNNERS[e['runnerImage']] == e['system'], 'runner platform must match native execution')
    job_capture = read_native_artifact(artifact_directory, public_base, e['jobArtifact'])
    log_capture = read_native_artifact(artifact_directory, public_base, e['logArtifact'])
    job_format = e['jobArtifact'].get('format', 'command-json')
    log_format = e['logArtifact'].get('format', 'command-json')
    require(job_format in ('command-json', 'job-json', 'jobs-json') and log_format in ('text', 'command-json'), 'job/log artifact formats must match actual content')
    if job_format == 'command-json':
        require(job_capture.get('exitCode') == 0, 'job metadata retrieval failed')
        job = json.loads(job_capture['stdout'])
    elif job_format == 'jobs-json':
        matches = [job for job in job_capture['jobs'] if job.get('html_url') == e['jobUrl']]
        require(len(matches) == 1, 'exact job missing from retained job list')
        job = matches[0]
    else:
        job = job_capture
    require(job.get('head_sha') == e['revision'] and job.get('html_url') == e['jobUrl'], 'foreign job source or identity')
    require(job.get('status') == 'completed' and job.get('conclusion') in ('success', 'failure'), 'completed successful or later-failed job required')
    require(job['conclusion'] != 'failure' or e.get('jobConclusion') == 'failure', 'failed overall job must remain explicitly recorded')
    require(e.get('jobConclusion') is None or e['jobConclusion'] == job['conclusion'], 'overall job conclusion must remain accurate')
    api = 'repos/' + e['repository'] + '/actions/jobs/' + str(job['id'])
    if job_format == 'command-json':
        require(job_capture.get('command') == ['gh', 'api', api], 'job capture command must bind exact repository/job')
    else:
        require(job.get('url') == 'https://api.github.com/' + api, 'metadata must bind exact repository/job API identity')
    if log_format == 'command-json':
        require(log_capture.get('exitCode') == 0 and log_capture.get('command') in (['gh', 'api', api + '/logs'], ['gh', 'api', api + '/logs', '--allow-escape-sequences']), 'log capture must bind exact repository/job')
        raw_log = log_capture['stdout']
    else:
        raw_log = log_capture
    require(e['jobUrl'].startswith('https://github.com/' + e['repository'] + '/actions/runs/'), 'job must belong to reviewed repository')
    if e.get('logJobName') is not None:
        require(e['logJobName'] == job['name'], 'grouped log selector must match exact job')
        selected = [line.split('\t', 2)[2] for line in raw_log.splitlines() if line.startswith(e['logJobName'] + '\t') and len(line.split('\t', 2)) == 3]
        raw_log = '\n'.join(selected) + '\n'
    matches = [s for s in job['steps'] if s['number'] == e['stepNumber']]
    require(len(matches) == 1, 'exact executed step missing')
    step = matches[0]
    require(step['status'] == 'completed' and step['conclusion'] == 'success' and step['name'] == (e.get('stepName') or 'Run ' + e['command']), 'step must actually run the supported native build command successfully')
    log = re.sub(r'(?:\x1b|\^\[)\[[0-9;]*m', '', raw_log)
    require(e['revision'] in log and ('repository: ' + e['repository'] in log or 'Syncing repository: ' + e['repository'] in log), 'checkout source missing from retained log')
    require('Image: ' + e['runnerImage'] + '\n' in log, 'native runner image missing from retained log')
    start, end = timestamp(step['started_at']), timestamp(step['completed_at']) + timedelta(seconds=1)
    later_starts = [timestamp(s['started_at']) for s in job['steps'] if s.get('number', 0) > e['stepNumber'] and s.get('started_at')]
    if later_starts:
        end = min(end, min(later_starts))
    lines = []
    for line in log.splitlines():
        parts = line.split(' ', 1)
        if len(parts) == 2:
            try:
                instant = timestamp(parts[0].lstrip('\ufeff'))
            except ValueError:
                continue
            if start <= instant < end:
                lines.append(parts[1])
    logical, pending = [], ''
    for line in lines:
        part = line.strip()
        if part.endswith('\\'):
            pending += part[:-1].rstrip() + ' '
        else:
            logical.append(pending + part)
            pending = ''
    require(e['command'] in logical, 'executed command absent from successful step log')
    if scripted:
        assertions = e.get('runtimeAssertions', [])
        require(isinstance(assertions, list) and all(text(line) for line in assertions), 'script derivation needs observed runtime assertions')
        # SDK roles come from inspected invocation/input bindings. Some checks assert
        # silently; recorded stdout assertions corroborate execution when available.
        proof_lines = lines
        if check.get('executionArtifact') is not None:
            require(all(check.get(k) is not None for k in ('reportArtifact', 'artifactMetadata', 'artifactName')), 'archived script proof requires actual report and artifact metadata')
            transcript = read_native_artifact(artifact_directory, public_base, check['executionArtifact'])
            report = read_native_artifact(artifact_directory, public_base, check['reportArtifact'])
            metadata = read_native_artifact(artifact_directory, public_base, check['artifactMetadata'])
            require(isinstance(transcript, str) and isinstance(report, dict) and report.get('selectedCasesPassed') is True, 'actual completed script transcript/report required')
            archive_matches = [artifact for artifact in metadata['artifacts'] if artifact['name'] == check['artifactName']]
            require(len(archive_matches) == 1, 'exact uploaded artifact metadata required')
            archive = archive_matches[0]
            require(archive['workflow_run']['id'] == job['run_id'] and archive['workflow_run']['head_sha'] == e['revision'] and archive['name'] in log and timestamp(archive['created_at']) >= timestamp(step['completed_at']), 'archived proof must bind actual job run/source and subsequent upload')
            proof_lines = re.sub(r'(?:\x1b|\^\[)\[[0-9;]*m', '', transcript).splitlines()
        markers = [index for index, line in enumerate(proof_lines) if line == "building '" + e['drvPath'] + "'..."]
        structured = check.get('transcriptLayout') == 'argv-stdout-stderr'
        require((check.get('buildArgv') is None and check.get('transcriptLayout') is None) or
                (structured and check.get('executionArtifact') is not None and
                 isinstance(check.get('buildArgv'), list) and check['buildArgv'][:2] == ['nix', 'build'] and
                 all(text(arg) for arg in check['buildArgv']) and 'result.stdout + result.stderr' in generator),
                'declared command/stdout/stderr layout must bind actual generator source and Nix build argv')
        if structured:
            blocks, current = [], None
            for line in proof_lines:
                try:
                    args = json.loads(line) if line.startswith('[') else None
                except ValueError:
                    args = None
                if isinstance(args, list) and args and all(isinstance(arg, str) for arg in args):
                    if current is not None:
                        blocks.append(current)
                    current = {'argv': args, 'lines': []}
                elif current is not None:
                    current['lines'].append(line)
            if current is not None:
                blocks.append(current)
            require(any(block['argv'] == check['buildArgv'] and
                        "building '" + e['drvPath'] + "'..." in block['lines'] and
                        all(path in block['lines'] for path in e['observedOutputs'].values())
                        for block in blocks), 'observed drv and output must bind the same actual Nix build command/result block')
        else:
            require(markers and all(any(index > markers[0] and line == path for index, line in enumerate(proof_lines))
                                    for path in e['observedOutputs'].values()), 'chronological output observation must follow the actual built drv')
        require(markers and all(any(index > markers[0] and line == assertion for index, line in enumerate(proof_lines)) for assertion in assertions), 'actual built derivation and runtime assertions must bind successful script step')
        return e
    # Flake-check success establishes realization (possibly cached), not a fresh rebuild.
    # Pair the exact attribute with its next evaluated drv, permitting fetch warnings.
    # A later attribute starts a new binding; unrelated derivations cannot satisfy it.
    pair = "checking derivation " + e['check'] + '...'
    current, matched = None, False
    for line in lines:
        if line.startswith('checking derivation '):
            current = line
        elif line.startswith('derivation evaluated to '):
            if current == pair and line == 'derivation evaluated to ' + e['drvPath']:
                matched = True
            current = None
    require(matched, 'check and derivation are not paired in successful build step')
    return e
