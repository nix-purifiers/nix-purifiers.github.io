"""Executable receipts for completed quality reviews.

Structural validation binds evidence; it does not independently authenticate receipts.
The integrator must inspect their contents before accepting an assessment.
"""
from html import escape
import re
import hashlib

CRITERIA = ('evaluation', 'goodTests', 'linux', 'darwin', 'oneVersion',
            'nonEolVersions', 'manySamples', 'longCompatibility')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def url(value):
    return isinstance(value, str) and re.fullmatch(r'https://[^\s<>"|]+', value) is not None


def digest(value):
    return isinstance(value, str) and re.fullmatch(r'sha256-[A-Za-z0-9+/]{43}=', value) is not None


def store(value, drv=False):
    return isinstance(value, str) and re.fullmatch(
        r'/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+' + (r'\.drv' if drv else ''), value) is not None


def validate_receipt(e, artifact_directory=None, public_base=None):
    if isinstance(e, dict) and e.get('kind') == 'native-ci-execution':
        from native_ci_evidence import validate_native_ci
        require(artifact_directory is not None and public_base is not None,
                'native CI validation requires retained artifacts')
        return validate_native_ci(e, artifact_directory, public_base)
    require(isinstance(e, dict) and set(e) == {
        'repository', 'revision', 'system', 'check', 'drvPath', 'outputs',
        'sdkVersions', 'sampleSources', 'sourceNarHash', 'outputNarHashes', 'evaluation', 'build'}, 'derivation evidence has missing or unknown fields')
    require(isinstance(e['repository'], str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', e['repository']), 'invalid source repository')
    require(isinstance(e['revision'], str) and re.fullmatch(r'[0-9a-f]{40}', e['revision']), 'evidence needs immutable revision')
    require(isinstance(e['system'], str) and re.fullmatch(r'(x86_64|aarch64)-(linux|darwin)', e['system']), 'unsupported evidence system')
    require(isinstance(e['check'], dict) and set(e['check']) == {'kind', 'value', 'replay'} and
            e['check']['kind'] in ('flake-attribute', 'expression') and text(e['check']['value']), 'exact check attribute or expression required')
    replay = e['check']['replay']
    if e['check']['kind'] == 'expression':
        require(isinstance(replay, dict) and set(replay) == {'artifactUrl', 'artifactSha256', 'expressionSha256', 'arguments'}, 'expression requires retained replay inputs/source/lock artifact')
        require(url(replay['artifactUrl']) and isinstance(replay['artifactSha256'], str) and re.fullmatch(r'[0-9a-f]{64}', replay['artifactSha256']), 'replay artifact must have content digest')
        require(replay['expressionSha256'] == hashlib.sha256(e['check']['value'].encode()).hexdigest(), 'expression hash mismatch')
        require(isinstance(replay['arguments'], dict) and all(text(k) and text(v) for k, v in replay['arguments'].items()), 'exact replay arguments required')
    else:
        require(replay is None, 'flake references use immutable repository/lock inputs')
    require(store(e['drvPath'], drv=True), 'exact derivation store path required')
    require(isinstance(e['outputs'], dict) and e['outputs'] and all(text(k) and store(v) and not v.endswith('.drv') for k, v in e['outputs'].items()), 'named derivation outputs required')
    require(isinstance(e['sdkVersions'], dict) and all(text(k) and text(v) for k, v in e['sdkVersions'].items()), 'SDK versions must be explicit strings')
    require(digest(e['sourceNarHash']), 'source NAR digest required')
    require(isinstance(e['outputNarHashes'], dict) and set(e['outputNarHashes']).issubset(e['outputs']) and all(digest(h) for h in e['outputNarHashes'].values()), 'invalid realized output NAR digests')
    require(isinstance(e['sampleSources'], list) and all(isinstance(s, dict) and set(s) == {'repository', 'revision', 'sourceNarHash'} and url(s['repository']) and isinstance(s['revision'], str) and re.fullmatch(r'[0-9a-f]{40}', s['revision']) and digest(s['sourceNarHash']) for s in e['sampleSources']), 'invalid sample source inputs')
    ev = e['evaluation']
    if ev is not None:
        require(isinstance(ev, dict) and set(ev) == {'sourceRevision', 'sourceNarHash', 'check', 'drvPath', 'receipt', 'artifactSha256'}, 'invalid evaluation receipt')
        require(ev['sourceRevision'] == e['revision'] and ev['sourceNarHash'] == e['sourceNarHash'] and ev['check'] == e['check'] and ev['drvPath'] == e['drvPath'], 'evaluation must bind exact source/check/derivation')
        require(url(ev['receipt']) and isinstance(ev['artifactSha256'], str) and re.fullmatch(r'[0-9a-f]{64}', ev['artifactSha256']), 'evaluation artifact and digest required')
    b = e['build']
    if b is None:
        require(not e['outputNarHashes'], 'evaluation alone cannot assert realized output hashes')
        return e
    require(isinstance(b, dict) and set(b) == {'status', 'executedSystem', 'sourceRevision', 'drvPath', 'outputs', 'receipt', 'artifactSha256', 'sourceNarHash', 'outputNarHashes', 'sdkVersions', 'sampleSources'}, 'build receipt has missing or unknown fields')
    require(b['status'] in ('success', 'failed', 'blocked'), 'invalid build result')
    require(b['sourceRevision'] == e['revision'] and b['drvPath'] == e['drvPath'], 'build must bind exact source and derivation')
    require(b['sourceNarHash'] == e['sourceNarHash'] and b['sdkVersions'] == e['sdkVersions'] and b['sampleSources'] == e['sampleSources'], 'build must bind source digest and SDK versions')
    require(isinstance(b['artifactSha256'], str) and re.fullmatch(r'[0-9a-f]{64}', b['artifactSha256']), 'receipt artifact SHA256 required')
    require(url(b['receipt']), 'build receipt must be an inspectable HTTPS artifact')
    require(isinstance(b['executedSystem'], str) and re.fullmatch(r'(x86_64|aarch64)-(linux|darwin)', b['executedSystem']), 'execution host must be identified')
    require(isinstance(b['outputs'], dict), 'build outputs must be named')
    if b['status'] == 'success':
        require(set(e['outputNarHashes']) == set(e['outputs']), 'successful build needs every realized output hash')
        require(b['outputNarHashes'] == e['outputNarHashes'], 'realized output hashes must match')
        require(b['outputs'] == e['outputs'], 'successful receipt must bind every realized output')
    else:
        require(not e['outputNarHashes'], 'failed build cannot assert realized output hashes')
        require(not b['outputNarHashes'], 'failed receipt cannot assert output hashes')
        require(not b['outputs'], 'failed or blocked receipt cannot assert realized outputs')
    return e


def native_success(e, artifact_directory=None, public_base=None):
    if isinstance(e, dict) and e.get('kind') == 'native-ci-execution':
        validate_receipt(e, artifact_directory, public_base)
        return True
    b = e['build']
    return b is not None and b['status'] == 'success' and b['executedSystem'] == e['system']


def validate_review(repository, revision, review, artifact_directory=None, public_base=None):
    """Validate a completed overlay; existing tier calculation remains authoritative.

    criteria references executable evidence IDs separately from explanatory sources.
    gap is mandatory only for not-met. Every claim binds the reviewed source.
    """
    require(isinstance(review, dict) and set(review) == {'derivations', 'criteria', 'sampleBuilds'}, 'invalid completed evidence review')
    evidence = review['derivations']
    require(isinstance(evidence, dict) and all(text(k) for k in evidence), 'derivations must have stable IDs')
    for e in evidence.values():
        validate_receipt(e, artifact_directory, public_base)
        require(e['repository'] == repository and e['revision'] == revision, 'stale or foreign derivation evidence')
    require(isinstance(review['sampleBuilds'], list), 'sampleBuilds must be a list')
    names = []
    for sample in review['sampleBuilds']:
        require(isinstance(sample, dict) and set(sample) == {'name', 'upstream', 'derivations'} and text(sample['name']), 'invalid sample identity')
        upstream = sample['upstream']
        require(isinstance(upstream, dict) and set(upstream) == {'repository', 'revision', 'sourceNarHash'} and digest(upstream['sourceNarHash']) and url(upstream['repository']) and isinstance(upstream['revision'], str) and re.fullmatch(r'[0-9a-f]{40}', upstream['revision']), 'sample needs immutable source identity')
        refs = sample['derivations']
        require(isinstance(refs, list) and refs and all(isinstance(ref, str) and ref in evidence and native_success(evidence[ref], artifact_directory, public_base) and upstream in evidence[ref].get('sampleSources', []) for ref in refs) and len(refs) == len(set(refs)), 'sample needs successful native derivations')
        names.append(sample['name'])
    require(len(names) == len(set(names)), 'duplicate samples')
    require(isinstance(review['criteria'], dict) and set(review['criteria']) == set(CRITERIA), 'every criterion requires completed review')
    for key, criterion in review['criteria'].items():
        require(isinstance(criterion, dict) and set(criterion) == {'state', 'summary', 'derivations', 'sources', 'gap'}, 'invalid completed criterion')
        require(criterion['state'] in ('met', 'not-met') and text(criterion['summary']), 'completed criterion requires judgment and rationale')
        refs = criterion['derivations']
        require(isinstance(refs, list) and all(isinstance(ref, str) and ref in evidence for ref in refs) and len(refs) == len(set(refs)), 'unknown or duplicate derivation reference')
        require(isinstance(criterion['sources'], list) and all(url(s) for s in criterion['sources']), 'invalid explanatory source')
        if criterion['state'] == 'not-met':
            require(text(criterion['gap']) and (refs or criterion['sources']), 'not-met needs a specific gap and inspected evidence')
            continue
        require(criterion['gap'] is None and refs, 'met needs executable evidence and no gap')
        bound = [evidence[ref] for ref in refs]
        if key == 'evaluation':
            require(all(e.get('kind') == 'native-ci-execution' or e['evaluation'] is not None or (e['build'] is not None and e['build']['status'] == 'success') for e in bound), 'evaluation needs a bound execution or evaluation receipt')
        if key == 'manySamples':
            require(review['sampleBuilds'] and all(any(ref in sample['derivations'] for sample in review['sampleBuilds']) for ref in refs), 'sample breadth must bind distinct sample identities')
        if key != 'evaluation':
            require(all(native_success(e, artifact_directory, public_base) for e in bound), 'capability claims need successful native build receipts')
        if key in ('linux', 'darwin'):
            require(all(e['system'].endswith('-' + key) for e in bound), 'platform evidence must match the claimed OS')
        if key in ('oneVersion', 'nonEolVersions', 'longCompatibility'):
            require(all(e.get('sdkVersions', {}) for e in bound), 'version claims require executed SDK version bindings')
        if key == 'nonEolVersions':
            require(criterion['sources'], 'non-EOL judgment requires upstream policy sources')
    return review


def render_receipts(review):
    """Render already validated receipts, never promote a link into a result."""
    lines = []
    for name, e in review['derivations'].items():
        if isinstance(e, dict) and e.get('kind') == 'native-ci-execution':
            check = e['check']
            check_text = (check['scriptPath'] + ' ' + check['arguments']) if isinstance(check, dict) else check
            outcome = 'Native CI check succeeded; output hashes not recorded'
            if e.get('jobConclusion') == 'failure':
                outcome += '; a later job step failed'
            details = [name, outcome, e['system'], e['revision'], check_text, e['drvPath']]
            if isinstance(check, dict):
                details += ['Generator SHA256: ' + check['scriptArtifact']['artifactSha256'],
                            'Source lock SHA256: ' + check['lockArtifact']['artifactSha256'], check['replayNotes']]
            details += ['Predicted ' + key + ': ' + value for key, value in e['predictedOutputs'].items()]
            details += ['Observed ' + key + ': ' + value for key, value in e['observedOutputs'].items()]
            details += [key + ' ' + value for key, value in e.get('sdkVersions', {}).items()]
            if e.get('sourceNarHash'):
                details += ['Source NAR: ' + e['sourceNarHash']]
            links = [(e['jobUrl'], 'Native CI job'),
                     (e['logArtifact']['receipt'], 'Retained execution log')]
            if isinstance(check, dict):
                links += [(check['sourceUrl'], 'Immutable executable generator'),
                          (check['scriptArtifact']['receipt'], 'Retained generator bytes'),
                          (check['lockArtifact']['receipt'], 'Source root lock')]
                for field, label in (('executionArtifact', 'Derivation execution transcript'),
                                     ('reportArtifact', 'Execution report')):
                    if check.get(field):
                        links.append((check[field]['receipt'], label))
            lines.append('<p>' + '<br>'.join(escape(item) for item in details) +
                         ''.join('<br><a href="' + escape(url, quote=True) + '">' + label + '</a>'
                                 for url, label in links) + '</p>')
            continue
        b = e['build']
        result = ('Receipt reports derivation evaluation; no build receipt' if e['evaluation'] else 'Declared derivation; no execution receipt') if b is None else (
            'Receipt reports native build success (local realization; outputs may be reused)' if native_success(e) else
            'Receipt reports build success on ' + b['executedSystem'] if b['status'] == 'success' else
            'Build ' + b['status'])
        details = [name, result, e['system'], e['revision'], e['check']['value'], e['drvPath']]
        details += [f'{key}: {value}' for key, value in e['outputs'].items()]
        details += [f'{key} {value}' for key, value in e['sdkVersions'].items()]
        details += ['Source NAR: ' + e['sourceNarHash']]
        details += [f'{key} NAR: {value}' for key, value in e['outputNarHashes'].items()]
        if b:
            details += ['Receipt SHA256: ' + b['artifactSha256']]
        if e['evaluation']:
            details += ['Evaluation receipt SHA256: ' + e['evaluation']['artifactSha256']]
        lines.append('<p>' + '<br>'.join(escape(item) for item in details) +
                     (f'<br><a href="{escape(b["receipt"], quote=True)}">Build receipt</a>' if b else '') +
                     (f'<br><a href="{escape(e["evaluation"]["receipt"], quote=True)}">Evaluation receipt</a>' if e['evaluation'] else '') + '</p>')
    return '\n'.join(lines)
