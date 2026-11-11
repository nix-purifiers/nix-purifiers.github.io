"""Explicit audit provenance; historical compatibility observations stay immutable."""
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess

from compatibility_evidence import input_digest, runner_system, validate_registry

PAGES = 'pages-only-equivalence-reviewed-not-retested'
CURRENT = 'current-observation-verified'
PARTIAL = 'current-native-case-proven-selected-output-join-incomplete'
DRIFT = 'runtime-drift-current-derivation-unjoined'
MATCH = 'source-inputs-match'
SHA = re.compile(r'[0-9a-f]{64}')
REV = re.compile(r'[0-9a-f]{40}')
NAR = re.compile(r'sha256-[A-Za-z0-9+/]{43}=')
RECONCILED_REGISTRY_SHA = 'cf9f0c050bfb8c20c743ebe6833c499047beeb3e4b3fcf4de57655aafe9a802c'
HISTORICAL_REGISTRY_SHA = 'f2ea7676cda5942a7c5895b4d077afbeae5b0be2d07aae30263b2b5abdf7f64c'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected.split()), 'unexpected reconciliation fields')


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Reconciliation:
    def __init__(self, sidecar, registry_bytes, root, catalog=None):
        self.root = Path(root)
        self.data = sidecar
        fields(sidecar, 'version registrySha256 reviewBindings pagesEquivalences currentObservations unresolved')
        require(sidecar['version'] == 1, 'unsupported reconciliation version')
        require(sidecar['registrySha256'] == RECONCILED_REGISTRY_SHA, 'frozen registry anchor changed')
        registry = json.loads(registry_bytes)
        historical = registry
        historical_bytes = registry_bytes
        if digest(registry_bytes) != sidecar['registrySha256']:
            reference = {'artifactSha256': RECONCILED_REGISTRY_SHA,
                         'path': f'docs-site/evidence/{RECONCILED_REGISTRY_SHA}.json'}
            historical = self.asset(reference)
            historical_bytes = (self.root / reference['path']).read_bytes()
            self.validate_append_only(historical, registry)
            if catalog is None:
                catalog = json.loads((self.root / 'docs-site/catalog.json').read_text())['catalog']
            # Additions use the ordinary typed, source-inventory and scoped CI
            # bindings. The audit's --verify-ci still rechecks every review.
            validate_registry(registry, catalog)
        # The reviewed partition belongs to its frozen snapshot, not the size
        # of today's registry. New points receive no historical annotations.
        self.points = {(name, p['id']): p for name, item in historical['projects'].items() for p in item['testedPoints']}
        self.reviews = {(name, p): r for name, item in registry['projects'].items() for r in item['reviews'] for p in r['pointIds']}
        require(len(sidecar['reviewBindings']) == 1, 'one immutable reviewed projection required')
        projection = self.asset(sidecar['reviewBindings'][0])
        fields(projection, 'kind derivedFromReviewSha256 projectionMeaning counts pagesEquivalences currentObservations unresolved historicalRegistrySha256 registryExtensionReview')
        require(projection['kind'] == 'reviewed-reconciliation-projection', 'wrong projection kind')
        require(SHA.fullmatch(projection['derivedFromReviewSha256']) is not None, 'missing original review digest')
        require(projection['historicalRegistrySha256'] == sidecar['registrySha256'], 'projection registry mismatch')
        for key in ['pagesEquivalences', 'currentObservations', 'unresolved']:
            require(projection[key] == sidecar[key], 'sidecar differs from immutable reviewed projection')
        self.validate_registry_extension(self.asset(projection['registryExtensionReview']), historical, historical_bytes)
        self.annotations = {}
        self.ids = set()
        for equivalence in sidecar['pagesEquivalences']:
            self.validate_pages(equivalence)
        for observation in sidecar['currentObservations']:
            self.validate_current(observation)
        for unresolved in sidecar['unresolved']:
            expected = 'project historicalPointId observedRevision status reason'
            if unresolved.get('status') == PARTIAL:
                expected += ' partialEvidence'
                report = self.asset(unresolved['partialEvidence'])
                require(report['source']['revision'] == unresolved['observedRevision'], 'partial source mismatch')
                require(report['selectedCasesPassed'] is True, 'partial native case failed')
            fields(unresolved, expected)
            require(unresolved['status'] in [PARTIAL, DRIFT], 'unresolved observation cannot claim completion')
            require(bool(unresolved['reason'].strip()), 'missing unresolved reason')
            self.add(unresolved['project'], unresolved['historicalPointId'], unresolved)
        # Exact matches need no annotation. Other points must not silently disappear.
        counts = {PAGES: sum(len(x['historicalPointIds']) for x in sidecar['pagesEquivalences']),
                  'current-derivation-and-native-case-joined': len(sidecar['currentObservations']),
                  PARTIAL: sum(x['status'] == PARTIAL for x in sidecar['unresolved']),
                  DRIFT: sum(x['status'] == DRIFT for x in sidecar['unresolved']),
                  MATCH: len(self.points) - len(self.annotations)}
        require(counts == projection['counts'], 'reviewed point partition mismatch')

    @staticmethod
    def validate_append_only(historical, current):
        """Existing point/review encodings are immutable ordered prefixes."""
        fields(current, 'version projects')
        require(type(current['version']) is int and current['version'] == historical['version'] and isinstance(current['projects'], dict), 'historical registry changed')
        require(set(historical['projects']) <= set(current['projects']), 'historical registry project removed')
        added = 0
        for name, old in historical['projects'].items():
            new = current['projects'][name]
            fields(new, 'testedPoints reviews')
            for key in ['testedPoints', 'reviews']:
                require(isinstance(new[key], list), 'historical registry changed')
                prefix = new[key][:len(old[key])]
                # Preserve JSON types and key order as well as values; bools
                # and numbers must not compare equal by Python coercion.
                require(json.dumps(prefix, separators=(',', ':')) == json.dumps(old[key], separators=(',', ':')),
                        'historical registry point or review changed')
            added += len(new['testedPoints']) - len(old['testedPoints'])
        for name, entry in current['projects'].items():
            if name not in historical['projects']:
                fields(entry, 'testedPoints reviews')
                require(isinstance(entry['testedPoints'], list) and isinstance(entry['reviews'], list), 'invalid appended project')
                added += len(entry['testedPoints'])
        require(added > 0, 'historical registry changed without appended points')

    def validate_registry_extension(self, extension, registry, registry_bytes):
        """Retain the public125 identities; six reviewed runtime points are separate."""
        fields(extension, 'kind historicalRegistry extendedRegistrySha256 candidateSourceCommit addedProject addedPointIds addedSourceRevision addedSourceInputDigest addedReviewSha256 roleEvidence runtimeReceipts scope')
        require(extension['kind'] == 'reviewed-registry-extension' and extension['addedProject'] == 'sbt-purifier', 'unreviewed registry extension')
        require(extension['historicalRegistry']['artifactSha256'] == HISTORICAL_REGISTRY_SHA, 'historical registry anchor changed')
        historical = self.asset(extension['historicalRegistry'])
        require(digest(registry_bytes) == extension['extendedRegistrySha256'], 'extended registry digest mismatch')
        require(REV.fullmatch(extension['candidateSourceCommit']) is not None, 'missing reviewed parent commit')
        require(set(historical['projects']) == set(registry['projects']), 'registry project set changed')
        for name, old in historical['projects'].items():
            new = registry['projects'][name]
            if name != 'sbt-purifier':
                require(new == old, 'historical registry project changed')
            else:
                require(new['testedPoints'][:len(old['testedPoints'])] == old['testedPoints'] and new['reviews'][:len(old['reviews'])] == old['reviews'], 'historical SBT identities changed')
        old = historical['projects']['sbt-purifier']
        new = registry['projects']['sbt-purifier']
        added = new['testedPoints'][len(old['testedPoints']):]
        reviews = new['reviews'][len(old['reviews']):]
        require(len(added) == 6 and len(reviews) == 1, 'extension must contain six separate runtime points and one source review')
        ids = sorted(p['id'] for p in added)
        require(len(set(ids)) == 6 and ids == extension['addedPointIds'] and set(ids) == set(reviews[0]['pointIds']), 'added point coverage mismatch')
        review = reviews[0]
        require(review['sourceRevision'] == extension['addedSourceRevision'] and input_digest(review['files']) == review['inputDigest'] == extension['addedSourceInputDigest'], 'added source inventory mismatch')
        require(digest(json.dumps(review, sort_keys=True, separators=(',', ':')).encode()) == extension['addedReviewSha256'], 'added review binding mismatch')
        proof = self.asset(extension['roleEvidence'])
        require(proof['producer'] == extension['addedSourceRevision'] and proof['inputDigest'] == review['inputDigest'] and proof['sourceFiles'] == len(review['files']) and set(proof['newPointIds']) == set(ids) and proof['publicPoints'] == 125 and proof['finalPoints'] == 131, 'parent runtime proof scope mismatch')
        roles = {r['id']: r for r in proof['roles'] if r['role'] == 'runtime'}
        require(set(roles) == set(ids), 'runtime roles do not cover added points')
        refs = {r['pointId']: r['receipt'] for r in extension['runtimeReceipts']}
        require(len(extension['runtimeReceipts']) == len(refs) == 6 and set(refs) == set(ids), 'runtime receipt coverage mismatch')
        combinations = set()
        operations = ['native-lock', 'lock-reproducibility', 'native-prefetch', 'native-offline-build', 'project-build-scripts', 'project-test-scripts', 'pure-build']
        for point in added:
            role = roles[point['id']]
            require(refs[point['id']]['artifactSha256'] == role['receipt']['artifactSha256'], 'runtime receipt role mismatch')
            raw = self.asset(refs[point['id']])
            require(raw['complete'] is True and raw['sourceDiff'] == '' and raw['sourceRevision'] == point['sourceRevision'] == proof['producer'] and raw['sourceNarHash'] == proof['sourceNarHash'], 'runtime source proof mismatch')
            require(raw['system'] == point['system'] and raw['sbtVersion'] in ['1.11.7', '1.13.1', '2.0.12'] and point['system'] in ['x86_64-linux', 'aarch64-darwin'], 'unreviewed runtime tuple')
            require(point['id'] == f"native-runtime-sbt-{raw['sbtVersion']}-{point['system']}-{proof['producer'][:7]}" and point['operations'] == operations, 'runtime identity or operation scope expanded')
            require(len(point['components']) == 2 and point['components'][0] == {'role':'native-tool', 'name':'sbt', 'version':raw['sbtVersion']} and point['components'][1]['role'] == 'native-tool-runtime' and point['components'][1]['version'].split('.')[0] == raw['javaMajor'] == '21', 'runtime SDK roles changed')
            require(raw['derivation'] == role['derivation'] and raw['outputs'] == role['outputs'] and raw['derivation'].startswith('/nix/store/') and raw['derivation'].endswith('.drv'), 'runtime selected output identity mismatch')
            require(raw['outputs'] and all(path.startswith('/nix/store/') and NAR.fullmatch(value['narHash']) is not None for path, value in raw['outputs'].items()), 'runtime output NAR missing')
            require(any(job['id'] == role['jobId'] and job['system'] == point['system'] and job['conclusion'] == 'success' and f"https://github.com/nix-purifiers/sbt-purifier/actions/runs/{ci['runId']}/job/{job['id']}" in point['evidence'] for ci in review['ci'] for job in ci['jobs']), 'runtime CI point binding mismatch')
            combinations.add((raw['sbtVersion'], point['system']))
        require(len(combinations) == 6, 'duplicate runtime tuple')

    def asset(self, reference):
        fields(reference, 'artifactSha256 path')
        h = reference['artifactSha256']
        require(SHA.fullmatch(h) is not None and reference['path'] == f'docs-site/evidence/{h}.json', 'invalid evidence path')
        try:
            payload = (self.root / reference['path']).read_bytes()
        except OSError as error:
            raise ValueError('missing reconciliation evidence') from error
        require(digest(payload) == h, 'mutated reconciliation evidence')
        return json.loads(payload)

    def add(self, project, point_id, annotation):
        key = project, point_id
        require(key in self.points and key not in self.annotations, 'unknown or duplicate historical point')
        self.annotations[key] = annotation

    def identity(self, item):
        require(item['id'] not in self.ids, 'duplicate observation identity')
        self.ids.add(item['id'])
        require(REV.fullmatch(item.get('observedRevision', item.get('sourceRevision', ''))) is not None, 'invalid revision')
        require(item['reviewedAt'] == '2026-11-07', 'unreviewed observation date')

    def validate_pages(self, e):
        fields(e, 'id project historicalRevision historicalReviewInputDigest historicalPointIds observedRevision oldFullInputDigest newFullInputDigest runtimeInputDigest changedFiles reviewBinding reviewedAt')
        self.identity(e)
        require(e['id'] == f"pages:{e['project']}:{e['observedRevision']}", 'wrong equivalence identity')
        proof = self.asset(e['reviewBinding'])
        fields(proof, 'kind project historicalRevision observedRevision oldFiles newFiles runtimeInputDigest oldPage newPage patch claim')
        require(proof['kind'] == 'reviewed-pages-tree-comparison', 'wrong Pages evidence')
        for key in ['project', 'historicalRevision', 'observedRevision', 'runtimeInputDigest']:
            require(proof[key] == e[key], 'Pages binding mismatch')
        old, new = proof['oldFiles'], proof['newFiles']
        path = '.github/workflows/pages.yml'
        require(set(old) == set(new) and [k for k in sorted(old) if old[k] != new[k]] == [path], 'runtime inputs changed')
        require(input_digest(old) == e['oldFullInputDigest'] and input_digest(new) == e['newFullInputDigest'], 'full input digest mismatch')
        runtime = {k: v for k, v in old.items() if k != path}
        require(input_digest(runtime) == e['runtimeInputDigest'], 'runtime digest mismatch')
        # No arbitrary change within the Pages file is an equivalence. This is the
        # individually reviewed theme-ref replacement, including full file bytes.
        before = '7c553785354d3c85afc2185095f72946460eed5e'
        after = '968540041ecf1fcfeac494465a996029fd4b0fc3'
        require(proof['oldPage'].count(before) == 1 and proof['oldPage'].replace(before, after) == proof['newPage'], 'unreviewed Pages change')
        for content, mapping in [(proof['oldPage'], old), (proof['newPage'], new)]:
            require(digest(b'100644\0' + content.encode()) == mapping[path], 'Pages mode or content mismatch')
        require(e['changedFiles'] == [{'path': path, 'oldInputHash': old[path], 'newInputHash': new[path], 'patchSha256': digest(proof['patch'].encode())}], 'patch binding mismatch')
        require(e['historicalPointIds'], 'empty equivalence')
        for point_id in e['historicalPointIds']:
            review = self.reviews.get((e['project'], point_id))
            require(review and review['sourceRevision'] == e['historicalRevision'] and review['files'] == old and review['inputDigest'] == e['historicalReviewInputDigest'], 'historical Pages identity mismatch')
            self.add(e['project'], point_id, e)

    def validate_current(self, o):
        fields(o, 'id project historicalPointId sourceRevision sourceNarHash sourceInputDigest sourceTree system components operations derivations nativeCase reviewedAt limits')
        self.identity(o)
        require(o['id'] == f"current:{o['project']}:{o['historicalPointId']}:{o['sourceRevision']}", 'wrong current identity')
        point = self.points.get((o['project'], o['historicalPointId']))
        require(point is not None and o['sourceRevision'] != point['sourceRevision'], 'current observation must have separate source identity')
        for key in ['system', 'components', 'operations']:
            require(o[key] == point[key], 'current SDK/system/operation role mismatch')
        require(NAR.fullmatch(o['sourceNarHash']) is not None, 'invalid source NAR')
        tree = self.asset(o['sourceTree'])
        fields(tree, 'kind sourceRevision sourceFiles inputDigest')
        require(tree['kind'] == 'source-input-inventory' and tree['sourceRevision'] == o['sourceRevision'] and input_digest(tree['sourceFiles']) == tree['inputDigest'] == o['sourceInputDigest'], 'source inventory mismatch')
        fields(o['nativeCase'], 'sourceFiles ciStatus scope')
        scripts = {}
        for ref in o['nativeCase']['sourceFiles']:
            script = self.asset(ref)
            fields(script, 'kind sourceRevision sourceNarHash path sha256 content')
            require(script['kind'] == 'source-file' and script['sourceRevision'] == o['sourceRevision'] and script['sourceNarHash'] == o['sourceNarHash'], 'script source role mismatch')
            require(digest(script['content'].encode()) == script['sha256'], 'script content mismatch')
            require(tree['sourceFiles'].get(script['path']) in [digest(mode + b'\0' + script['content'].encode()) for mode in [b'100644', b'100755']], 'script not in bound source tree')
            scripts[script['path']] = script
        required = ['tests/node-lts-native.py', 'tests/legacy-native.py', 'tests/legacy-node.nix', '.github/workflows/check.yml'] if o['project'] == 'npm-purifier' else ['tests/compatibility/check.py', '.github/workflows/check.yml']
        require(set(scripts) == set(required), 'native driver source set mismatch')
        ci = self.asset(o['nativeCase']['ciStatus'])
        require(ci['headSha'] == o['sourceRevision'] and ci['conclusion'] == 'success', 'native CI source/conclusion mismatch')
        jobs = ci['jobs']
        require(o['derivations'], 'no realized selected output')
        require(len(o['derivations']) == (1 if o['project'] == 'npm-purifier' else 2), 'missing required baseline or composition derivation')
        seen_derivations = set()
        for index, entry in enumerate(o['derivations']):
            fields(entry, 'binding rawReceipt' + (' replay' if o['project'] == 'maven-purifier' else ''))
            b, raw = self.asset(entry['binding']), self.asset(entry['rawReceipt'])
            require(b['drvPath'] not in seen_derivations, 'duplicate baseline derivation')
            seen_derivations.add(b['drvPath'])
            require(b['status'] == 'success' and b['sourceRevision'] == raw['sourceRevision'] == o['sourceRevision'] and b['executedSystem'] == o['system'] and b['sourceNarHash'] == o['sourceNarHash'], 'derivation source/system mismatch')
            require(b['drvPath'].startswith('/nix/store/') and b['drvPath'].endswith('.drv') and b['outputs'] and set(b['outputs']) == set(b['outputNarHashes']), 'missing realized output identity')
            if o['project'] == 'npm-purifier':
                version = next(c['version'] for c in o['components'] if c['role'] == 'project-runtime')
                npm = next(c['version'] for c in o['components'] if c['name'] == 'npm')
                major = version.split('.')[0]
                require(b['sdkVersions'] == {'observed toolchain Node.js': version, 'observed toolchain npm': npm}, 'npm SDK roles changed')
                require(b['check']['value'] == f"checks.{o['system']}.node-lts-{major}", 'wrong native target')
                require(raw['trackedSourceClean'] and raw['system'] == o['system'], 'unclean or wrong runtime source')
                record = next((x for x in raw['checks'] if x['attribute'] == '.#' + b['check']['value']), None)
                require(record is not None, 'missing actual runtime record')
                for name, path in b['outputs'].items():
                    require(record['pathInfo'].get(path, {}).get('narHash') == b['outputNarHashes'][name], 'selected output NAR not realized')
                runner = 'ubuntu-latest' if o['system'] == 'x86_64-linux' else 'ubuntu-24.04-arm'
                require(any(j['name'] == f'legacy-native ({runner})' and j['conclusion'] == 'success' for j in jobs), 'native case CI missing')
            elif o['project'] == 'maven-purifier':
                version = next(c['version'] for c in o['components'] if c['name'] == 'Maven')
                java = next(c['version'] for c in o['components'] if c['role'] == 'native-tool-runtime')
                package = b['sdkVersions']['Java runtime']
                basename = Path(raw['javaHome']).name.split('-', 1)[-1]
                expected_major = java.split('.')[0].split('u')[0]
                actual_major = re.fullmatch(r'openjdk-headless-(\d+)(?:[u.].*)?', package)
                require(raw['mavenVersion'] == b['sdkVersions']['Maven'] == version and actual_major is not None and actual_major[1] == expected_major and basename == package and raw['sandbox'] == 'true', 'Maven SDK roles changed')
                require(NAR.fullmatch(raw.get('javaIdentity', {}).get(raw['javaHome'], {}).get('narHash', '')) is not None, 'Java identity missing')
                require(raw.get('sourceIdentity', {}).get(raw['sourcePath'], {}).get('narHash') == o['sourceNarHash'], 'source NAR role mismatch')
                replay = self.asset(entry['replay'])
                require(entry['replay']['artifactSha256'] == b['check']['replay']['artifactSha256'], 'replay binding mismatch')
                require(replay['revision'] == o['sourceRevision'] and replay['sourceNarHash'] == o['sourceNarHash'] and replay['actualBuildReceipt']['artifactSha256'] == entry['rawReceipt']['artifactSha256'], 'snapshot source/receipt mismatch')
                expression = b['check']['value']
                baseline = '\n      let\n        f = builtins.getFlake ("path:" + builtins.getEnv "COMPAT_FLAKE");\n        p = import f.inputs.nixpkgs {\n          system = builtins.currentSystem;\n          overlays = [ f.overlays.default ];\n        };\n      in (p.maven-purifier.buildMavenProject {\n        src = /. + builtins.getEnv "COMPAT_PROJECT";\n      }).tests\n    '
                composition = baseline.replace('COMPAT_PROJECT";', 'COMPAT_PROJECT"; projectDependencies = [ f.checks.${builtins.currentSystem}.composition.producer ];')
                if not version.startswith('2.'):
                    composition = '\n      let\n        f = builtins.getFlake ("path:" + builtins.getEnv "COMPAT_FLAKE");\n        p = import f.inputs.nixpkgs {\n          system = builtins.currentSystem;\n          overlays = [ f.overlays.default ];\n        };\n      built = p.maven-purifier.buildMavenProject {\n        src = /. + builtins.getEnv "COMPAT_PROJECT";\n      };\n          in p.runCommand "maven-compatibility-runtime" { tests = built.tests; } \'\'\n            find ${built.projections.maven}/org/apache/commons/commons-text -name \'*-nix-*.pom\' | grep -q .\n            touch $out\n          \'\' \n    '
                require(b['check']['kind'] == 'expression' and expression == [baseline, composition][index] and replay['expression'] == expression and digest(expression.encode()) == b['check']['replay']['expressionSha256'], 'baseline/composition expression mismatch')
                require(raw['projectSnapshot'] == f'project-{index}' and raw['command'] == replay['command'] == ['nix', 'build', '--impure', '--no-link', '--json', '--print-build-logs', '--expr', expression], 'snapshot command/role mismatch')
                require(raw['boundEnvironment'] == replay['originalBoundEnvironment'] == b['check']['replay']['arguments'] and raw['boundEnvironment']['COMPAT_FLAKE'] == raw['sourcePath'], 'snapshot arguments mismatch')
                project_files = replay['projectFiles']
                require({'pom.xml', 'maven-purifier.lock.json'} <= set(project_files), 'missing project snapshot')
                for path, file in project_files.items():
                    fields(file, 'encoding content sha256 executable')
                    require(not Path(path).is_absolute() and '..' not in Path(path).parts and file['encoding'] == 'base64', 'invalid snapshot file')
                    try:
                        content = base64.b64decode(file['content'], validate=True)
                    except ValueError as error:
                        raise ValueError('invalid snapshot encoding') from error
                    require(digest(content) == file['sha256'] and isinstance(file['executable'], bool), 'snapshot bytes/mode mismatch')
                derivation = raw['derivations']['derivations'].get(Path(b['drvPath']).name)
                require(derivation is not None, 'project snapshot not joined to derivation')
                if index == 0 or version.startswith('2.'):
                    require(derivation['env']['src'] == replay['expectedFilteredInputSource'], 'project snapshot not joined to derivation')
                else:
                    require(derivation['env']['tests'].startswith('/nix/store/') and 'commons-text' in derivation['env']['buildCommand'], 'composition wrapper role missing')
                record = next((x for x in raw['builds'] if x['drvPath'] == b['drvPath']), None)
                for name, path in b['outputs'].items():
                    require(raw['outputs'].get(path, {}).get('narHash') == b['outputNarHashes'][name], 'selected output NAR not realized')
                require(b['jobConclusion'] == 'success' and any(str(j['databaseId']) == b['jobUrl'].rsplit('/', 1)[-1] and j['conclusion'] == 'success' for j in jobs), 'Maven native case CI missing')
                if version.startswith('2.'):
                    require('native-input-composition' not in o['operations'] and b['nativeInputActivation'] == 'not claimed; builder-only for Maven 2', 'Maven2 scope expanded')
            else:
                raise ValueError('unreviewed current project')
            require(record is not None and record['drvPath'] == b['drvPath'] and record['outputs'] == b['outputs'], 'actual derivation/output mismatch')
            for name, nar in b['outputNarHashes'].items():
                require(NAR.fullmatch(nar) is not None and b['outputs'][name].startswith('/nix/store/'), 'invalid selected output')
        self.add(o['project'], o['historicalPointId'], o)

    def classify(self, project, point_id, revision, observed_files):
        """Exact observed commit AND inventory required; no descendant inheritance."""
        key = project, point_id
        review = self.reviews[key]
        if observed_files == review['files']:
            return {'status': MATCH, 'testedRevision': review['sourceRevision']}
        annotation = self.annotations.get(key)
        if annotation is None:
            return {'status': DRIFT, 'reason': 'No reviewed current binding'}
        target = annotation.get('observedRevision', annotation.get('sourceRevision'))
        if revision != target:
            return {'status': DRIFT, 'reason': 'Observed commit differs from reviewed exact revision'}
        if 'historicalPointIds' in annotation:
            proof = self.asset(annotation['reviewBinding'])
            require(observed_files == proof['newFiles'], 'observed Pages inputs differ from reviewed tree')
            return {'status': PAGES, 'equivalenceId': annotation['id'], 'retested': False, 'derivationEqualityClaimed': False}
        if 'derivations' in annotation:
            require(input_digest(observed_files) == annotation['sourceInputDigest'], 'observed current inputs differ from reviewed tree')
            return {'status': CURRENT, 'observationId': annotation['id'], 'sourceRevision': target}
        return {'status': annotation['status'], 'reason': annotation['reason']}

    def verify_current_ci(self, project):
        """Recheck exact recorded jobs; never trigger a workflow or execute tests."""
        checked = set()
        for observation in self.data['currentObservations']:
            if observation['project'] != project:
                continue
            ci = self.asset(observation['nativeCase']['ciStatus'])
            relevant_jobs = set()
            for entry in observation['derivations']:
                b = self.asset(entry['binding'])
                relevant_jobs.add(int(b.get('actualJob', b.get('jobUrl')).rsplit('/', 1)[-1]))
            if project == 'npm-purifier':
                runner = 'ubuntu-latest' if observation['system'] == 'x86_64-linux' else 'ubuntu-24.04-arm'
                native_jobs = [j for j in ci['jobs'] if j['name'] == f'legacy-native ({runner})']
                require(len(native_jobs) == 1, 'selected native job missing from recorded CI')
                relevant_jobs.add(native_jobs[0]['databaseId'])
            run_id = int(ci['jobs'][0]['url'].split('/actions/runs/')[1].split('/')[0])
            repository = f'nix-purifiers/{project}'
            actual = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repository}/actions/runs/{run_id}'], text=True))
            require(actual['head_sha'] == observation['sourceRevision'] and actual['conclusion'] == 'success' and actual['status'] == 'completed', 'current native CI no longer verified')
            require(relevant_jobs and relevant_jobs <= {j['databaseId'] for j in ci['jobs']}, 'selected current job missing from recorded CI')
            for job in ci['jobs']:
                if job['databaseId'] not in relevant_jobs or job['databaseId'] in checked:
                    continue
                actual_job = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repository}/actions/jobs/{job["databaseId"]}'], text=True))
                checked.add(job['databaseId'])
                require(actual_job['run_id'] == run_id and actual_job['head_sha'] == observation['sourceRevision'] and actual_job['conclusion'] == 'success' and actual_job['status'] == 'completed' and actual_job['name'] == job['name'] and runner_system(actual_job['labels']) == observation['system'] and actual_job['run_attempt'] == actual['run_attempt'], 'current native job no longer verified')
