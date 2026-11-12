import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from compatibility_reconciliation import Reconciliation, MATCH, PAGES, CURRENT, PARTIAL, DRIFT

ROOT = Path(__file__).resolve().parents[1]


class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current_registry = (ROOT/'model/compatibility-tests.json').read_bytes()
        cls.sidecar = json.loads((ROOT/'model/compatibility-reconciliation.json').read_text())
        cls.registry = (ROOT/'docs-site/evidence'/
                        (cls.sidecar['registrySha256'] + '.json')).read_bytes()
        cls.current_catalog = json.loads((ROOT/'docs-site/catalog.json').read_text())['catalog']
        cls.fixture_catalog = copy.deepcopy(cls.current_catalog)
        frozen_projects = json.loads(cls.registry)['projects']
        for name, page in cls.fixture_catalog.items():
            # The synthetic append uses the frozen registry, including the
            # absence of projects first added after that snapshot.
            page['compatibility']['testedPoints'] = copy.deepcopy(
                frozen_projects.get(name, {}).get('testedPoints', []))
        cls.real = Reconciliation(cls.sidecar, cls.current_registry, ROOT, catalog=cls.current_catalog)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = copy.deepcopy(self.sidecar)
        self.pending = {}

    def write_asset(self, value):
        payload = (json.dumps(value, indent=2)+'\n').encode()
        h = hashlib.sha256(payload).hexdigest()
        path = f'docs-site/evidence/{h}.json'
        self.pending[path] = payload
        return {'artifactSha256': h, 'path': path}

    def load(self, ref):
        return json.loads(self.pending[ref['path']]) if ref['path'] in self.pending else self.real.asset(ref)

    def validate(self, republish=False):
        # A changed reviewed projection is insufficient to legalize wrong roles:
        # these tests rebind it to exercise semantic checks below hash checking.
        if republish:
            p = self.load(self.data['reviewBindings'][0])
            for key in ['pagesEquivalences', 'currentObservations', 'unresolved']:
                p[key] = copy.deepcopy(self.data[key])
            self.data['reviewBindings'] = [self.write_asset(p)]
        for path, payload in self.pending.items():
            target = self.root/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        # Fall through to immutable real assets without copying the whole site.
        original = Reconciliation.asset
        def asset(obj, ref):
            if ref['path'] not in self.pending:
                return original(self.real, ref)
            return original(obj, ref)
        with patch.object(Reconciliation, 'asset', asset):
            return Reconciliation(self.data, self.registry, self.root, catalog=getattr(self, 'catalog', None))

    def append_fixture(self, project='maven-purifier'):
        # A synthetic additive unit fixture reuses existing scoped evidence;
        # it is never written to the public registry or presented as a retest.
        registry = json.loads(type(self).registry)
        entry = registry['projects'][project]
        added = copy.deepcopy(entry['testedPoints'][0])
        original_id = added['id']
        added['id'] = 'unit-additive-' + original_id
        review = copy.deepcopy(next(r for r in entry['reviews'] if original_id in r['pointIds']))
        review['pointIds'] = [added['id']]
        entry['testedPoints'].append(added)
        entry['reviews'].append(review)
        self.catalog = copy.deepcopy(self.fixture_catalog)
        self.catalog[project]['compatibility']['testedPoints'] = copy.deepcopy(entry['testedPoints'])
        self.pending['docs-site/evidence/' + self.sidecar['registrySha256'] + '.json'] = type(self).registry
        self.registry = (json.dumps(registry, indent=2)+'\n').encode()
        return registry, added, review

    def test_real_current_registry_preserves_frozen_history(self):
        frozen = json.loads(self.registry)['projects']
        frozen_points = {(name, point['id']): point
                         for name, entry in frozen.items() for point in entry['testedPoints']}
        self.assertEqual(self.real.points, frozen_points)
        current = json.loads(self.current_registry)['projects']
        for name, entry in current.items():
            for point in entry['testedPoints']:
                if (name, point['id']) in frozen_points:
                    continue
                review = self.real.reviews[name, point['id']]
                result = self.real.classify(name, point['id'], point['sourceRevision'], review['files'])
                self.assertEqual(result['status'], MATCH)
                self.assertNotIn((name, point['id']), self.real.annotations)

    def test_generic_reviewed_append_preserves_frozen_partition_and_annotations(self):
        for project in ['maven-purifier', 'sbt-purifier', 'cmake-purifier']:
            with self.subTest(project=project):
                registry, added, review = self.append_fixture(project)
                actual = self.validate()
                self.assertEqual(actual.points, self.real.points)
                self.assertEqual(actual.annotations, self.real.annotations)
                self.assertEqual(len(actual.points), 131)
                self.assertNotIn((project, added['id']), actual.points)
                self.assertEqual(actual.classify(project, added['id'], review['sourceRevision'], review['files'])['status'], MATCH)
                changed = dict(review['files'], **{'unreviewed-input': '0'*64})
                self.assertEqual(actual.classify(project, added['id'], review['sourceRevision'], changed)['status'], DRIFT)

    def test_append_cannot_mutate_remove_reorder_or_retype_old_history(self):
        for target in ['point', 'review', 'order', 'removed-project', 'json-type', 'sbt-runtime']:
            with self.subTest(target=target):
                registry, _, _ = self.append_fixture()
                item = registry['projects']['maven-purifier']
                if target == 'point':
                    item['testedPoints'][0]['notes'] += ' rewritten'
                elif target == 'review':
                    item['reviews'][0]['files']['invented-input'] = '0'*64
                elif target == 'order':
                    item['testedPoints'][0], item['testedPoints'][1] = item['testedPoints'][1], item['testedPoints'][0]
                elif target == 'removed-project':
                    del registry['projects']['sbt-purifier']
                elif target == 'json-type':
                    item['reviews'][0]['ci'][0]['attempt'] = True
                else:
                    registry['projects']['sbt-purifier']['testedPoints'][-1]['notes'] += ' rewritten'
                self.registry = (json.dumps(registry, indent=2)+'\n').encode()
                with self.assertRaisesRegex(ValueError, 'historical registry'):
                    self.validate()

    def test_append_still_requires_normal_catalog_source_and_ci_bindings(self):
        for target in ['source-digest', 'source-revision', 'ci-platform', 'unreviewed-point', 'catalog']:
            with self.subTest(target=target):
                registry, added, review = self.append_fixture()
                item = registry['projects']['maven-purifier']
                if target == 'source-digest':
                    review['inputDigest'] = '0'*64
                elif target == 'source-revision':
                    added['sourceRevision'] = '0'*40
                elif target == 'ci-platform':
                    for ci in review['ci']:
                        for job in ci['jobs']:
                            job['system'] = 'unrecorded-system'
                elif target == 'unreviewed-point':
                    item['reviews'].pop()
                else:
                    self.catalog['maven-purifier']['compatibility']['testedPoints'].pop()
                self.registry = (json.dumps(registry, indent=2)+'\n').encode()
                if target != 'catalog':
                    self.catalog['maven-purifier']['compatibility']['testedPoints'] = copy.deepcopy(item['testedPoints'])
                with self.assertRaises(ValueError):
                    self.validate()

    def test_new_point_cannot_be_restamped_as_a_historical_observation(self):
        _, added, _ = self.append_fixture()
        observation = copy.deepcopy(next(x for x in self.data['unresolved'] if x['status'] == DRIFT))
        observation.update(project='maven-purifier', historicalPointId=added['id'])
        self.data['unresolved'].append(observation)
        with self.assertRaisesRegex(ValueError, 'unknown or duplicate historical point'):
            self.validate(republish=True)

    def test_append_cannot_rebind_frozen_snapshot_or_restate_projection_counts(self):
        self.append_fixture()
        path = 'docs-site/evidence/' + self.sidecar['registrySha256'] + '.json'
        self.pending[path] += b' '
        with self.assertRaisesRegex(ValueError, 'mutated reconciliation evidence'):
            self.validate()
        self.pending[path] = type(self).registry
        projection = self.load(self.data['reviewBindings'][0])
        projection['counts'][MATCH] += 1
        self.data['reviewBindings'] = [self.write_asset(projection)]
        with self.assertRaisesRegex(ValueError, 'reviewed point partition mismatch'):
            self.validate()
        self.data = copy.deepcopy(self.sidecar)
        self.data['registrySha256'] = hashlib.sha256(self.registry).hexdigest()
        with self.assertRaisesRegex(ValueError, 'frozen registry anchor'):
            self.validate()

    def test_partition_preserves_all_131_recorded_observations(self):
        counts = {}
        for key, point in self.real.points.items():
            item = self.real.annotations.get(key)
            if item and 'historicalPointIds' in item:
                files = self.real.asset(item['reviewBinding'])['newFiles']
                rev = item['observedRevision']
            elif item and 'derivations' in item:
                files = self.real.asset(item['sourceTree'])['sourceFiles']
                rev = item['sourceRevision']
            elif item:
                files = dict(self.real.reviews[key]['files'], **{'unreviewed-change': '0'*64})
                rev = item['observedRevision']
            else:
                files = self.real.reviews[key]['files']
                rev = point['sourceRevision']
            result = self.real.classify(*key, rev, files)
            counts[result['status']] = counts.get(result['status'], 0)+1
        self.assertEqual(counts, {MATCH: 9, PAGES: 23, CURRENT: 10, PARTIAL: 1, DRIFT: 88})
        self.assertEqual(len(self.real.points), 131)

    def test_public125_registry_identities_remain_exact_after_extension(self):
        projection = self.real.asset(self.sidecar['reviewBindings'][0])
        extension = self.real.asset(projection['registryExtensionReview'])
        historical = self.real.asset(extension['historicalRegistry'])
        current = json.loads(self.registry)
        count = 0
        for name, item in historical['projects'].items():
            observed = current['projects'][name]
            self.assertEqual(observed['testedPoints'][:len(item['testedPoints'])], item['testedPoints'])
            self.assertEqual(observed['reviews'][:len(item['reviews'])], item['reviews'])
            count += len(item['testedPoints'])
        self.assertEqual(count, 125)

    def test_new_sbt_points_do_not_force_match_after_source_changes(self):
        for key, point in self.real.points.items():
            if not point['id'].endswith('-169b2e6'):
                continue
            files = copy.deepcopy(self.real.reviews[key]['files'])
            files['README.md'] = 'f'*64
            result = self.real.classify(*key, 'f'*40, files)
            self.assertEqual(result['status'], DRIFT)

    def mutate_extension(self, update):
        projection = self.load(self.data['reviewBindings'][0])
        extension = self.load(projection['registryExtensionReview'])
        update(extension)
        projection['registryExtensionReview'] = self.write_asset(extension)
        self.data['reviewBindings'] = [self.write_asset(projection)]

    def test_extension_cannot_change_public_history_or_expand_operations(self):
        for target in ['old-point', 'new-operations']:
            self.data = copy.deepcopy(self.sidecar)
            registry = json.loads(type(self).registry)
            project = registry['projects']['sbt-purifier']
            point = project['testedPoints'][0 if target == 'old-point' else -1]
            point['operations'] = point['operations'] + ['native-publish']
            self.registry = (json.dumps(registry, indent=2)+'\n').encode()
            changed_hash = hashlib.sha256(self.registry).hexdigest()
            self.data['registrySha256'] = changed_hash
            projection = self.load(self.data['reviewBindings'][0])
            projection['historicalRegistrySha256'] = changed_hash
            self.data['reviewBindings'] = [self.write_asset(projection)]
            self.mutate_extension(lambda e: e.update(extendedRegistrySha256=changed_hash))
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'frozen registry anchor|historical SBT identities|operation scope expanded'):
                self.validate(True)

    def test_registry_extension_cannot_substitute_its_historical_anchor(self):
        self.mutate_extension(lambda e: e.update(historicalRegistry=copy.deepcopy(e['roleEvidence'])))
        with self.assertRaisesRegex(ValueError, 'historical registry anchor'):
            self.validate(True)

    def test_runtime_extension_requires_real_source_bound_outputs(self):
        def mutate(extension):
            ref = extension['runtimeReceipts'][0]['receipt']
            raw = self.load(ref)
            raw['sourceRevision'] = 'f'*40
            extension['runtimeReceipts'][0]['receipt'] = self.write_asset(raw)
        self.mutate_extension(mutate)
        with self.assertRaisesRegex(ValueError, 'runtime receipt role mismatch'):
            self.validate(True)

    def test_original_registry_identity_cannot_be_changed(self):
        with self.assertRaisesRegex(ValueError, 'historical registry changed'):
            Reconciliation(self.sidecar, self.registry+b' ', ROOT)

    def test_sidecar_cannot_outgrow_immutable_review(self):
        self.data['currentObservations'][0]['system'] = 'aarch64-darwin'
        with self.assertRaisesRegex(ValueError, 'immutable reviewed projection'):
            self.validate()

    def test_exact_commit_equivalence_does_not_apply_to_descendant(self):
        e = self.sidecar['pagesEquivalences'][0]
        files = self.real.asset(e['reviewBinding'])['newFiles']
        result = self.real.classify(e['project'], e['historicalPointIds'][0], 'f'*40, files)
        self.assertEqual(result['status'], DRIFT)

    def test_runtime_or_mode_change_cannot_hide_behind_pages_path(self):
        e = self.sidecar['pagesEquivalences'][0]
        files = copy.deepcopy(self.real.asset(e['reviewBinding'])['newFiles'])
        files['flake.nix'] = 'a'*64
        with self.assertRaisesRegex(ValueError, 'observed Pages inputs differ'):
            self.real.classify(e['project'], e['historicalPointIds'][0], e['observedRevision'], files)

    def test_arbitrary_pages_change_is_rejected_even_with_new_hash(self):
        e = self.data['pagesEquivalences'][0]
        proof = self.load(e['reviewBinding'])
        proof['newPage'] += '\n# unrelated change\n'
        e['reviewBinding'] = self.write_asset(proof)
        with self.assertRaisesRegex(ValueError, 'unreviewed Pages change'):
            self.validate(True)

    def test_unknown_duplicate_or_removed_point_is_rejected(self):
        e = self.data['pagesEquivalences'][0]
        e['historicalPointIds'].append(e['historicalPointIds'][0])
        with self.assertRaisesRegex(ValueError, 'duplicate historical point'):
            self.validate(True)

    def test_current_sdk_system_and_operation_roles_are_preserved(self):
        for field, value in [('system', 'aarch64-darwin'), ('operations', ['pure-build']), ('components', [])]:
            with self.subTest(field=field):
                self.data = copy.deepcopy(self.sidecar)
                self.data['currentObservations'][0][field] = value
                with self.assertRaisesRegex(ValueError, 'role mismatch'):
                    self.validate(True)

    def test_wrong_native_source_script_is_rejected(self):
        o = self.data['currentObservations'][0]
        script = self.load(o['nativeCase']['sourceFiles'][0])
        script['content'] += '\n# changed\n'
        script['sha256'] = hashlib.sha256(script['content'].encode()).hexdigest()
        o['nativeCase']['sourceFiles'][0] = self.write_asset(script)
        with self.assertRaisesRegex(ValueError, 'not in bound source tree'):
            self.validate(True)

    def test_source_nar_cannot_replace_realized_output_nar(self):
        o = self.data['currentObservations'][0]
        b = self.load(o['derivations'][0]['binding'])
        b['outputNarHashes']['out'] = b['sourceNarHash']
        o['derivations'][0]['binding'] = self.write_asset(b)
        with self.assertRaisesRegex(ValueError, 'NAR not realized'):
            self.validate(True)

    def test_metadata_evaluation_cannot_replace_runtime_receipt(self):
        o = self.data['currentObservations'][0]
        b = self.load(o['derivations'][0]['binding'])
        b['status'] = 'evaluation-only'
        o['derivations'][0]['binding'] = self.write_asset(b)
        with self.assertRaisesRegex(ValueError, 'derivation source/system mismatch'):
            self.validate(True)

    def test_generic_success_at_wrong_source_does_not_prove_native_case(self):
        o = self.data['currentObservations'][0]
        ci = self.load(o['nativeCase']['ciStatus'])
        ci['headSha'] = 'f'*40
        o['nativeCase']['ciStatus'] = self.write_asset(ci)
        with self.assertRaisesRegex(ValueError, 'CI source/conclusion mismatch'):
            self.validate(True)

    def test_maven2_cannot_claim_native_input_activation(self):
        o = next(x for x in self.data['currentObservations'] if x['historicalPointId'] == 'maven-2.2.1-jdk-8')
        b = self.load(o['derivations'][0]['binding'])
        b['nativeInputActivation'] = 'native model activation'
        o['derivations'][0]['binding'] = self.write_asset(b)
        with self.assertRaisesRegex(ValueError, 'Maven2 scope expanded'):
            self.validate(True)

    def test_maven_missing_composition_or_duplicate_baseline_is_rejected(self):
        for mutation in ['missing-baseline', 'missing-composition', 'duplicate-baseline']:
            self.data = copy.deepcopy(self.sidecar)
            o = next(x for x in self.data['currentObservations'] if x['project'] == 'maven-purifier')
            if mutation == 'missing-baseline':
                o['derivations'] = o['derivations'][1:]
            elif mutation == 'missing-composition':
                o['derivations'] = o['derivations'][:1]
            else:
                o['derivations'][1] = copy.deepcopy(o['derivations'][0])
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'missing required|duplicate baseline'):
                self.validate(True)

    def test_maven_snapshot_swap_is_rejected(self):
        o = next(x for x in self.data['currentObservations'] if x['project'] == 'maven-purifier')
        o['derivations'][0]['replay'] = copy.deepcopy(o['derivations'][1]['replay'])
        with self.assertRaisesRegex(ValueError, 'replay binding mismatch'):
            self.validate(True)

    def test_maven_exact_java_and_source_identity_cannot_be_replaced(self):
        for mutation in ['wrong-major', 'wrong-patch', 'wrong-source-nar']:
            self.data = copy.deepcopy(self.sidecar)
            o = next(x for x in self.data['currentObservations'] if x['project'] == 'maven-purifier')
            raw = self.load(o['derivations'][0]['rawReceipt'])
            if mutation == 'wrong-source-nar':
                raw['sourceIdentity'][raw['sourcePath']]['narHash'] = 'sha256-'+'A'*43+'='
            else:
                raw['javaHome'] = raw['javaHome'].replace('8u504', '18u504' if mutation == 'wrong-major' else '8u505')
            o['derivations'][0]['rawReceipt'] = self.write_asset(raw)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'Maven SDK roles changed|source NAR role mismatch'):
                self.validate(True)

    def test_current_ci_api_accepts_exact_source_name_platform_attempt(self):
        requested = []
        def api(args, **kwargs):
            endpoint = args[-1]
            requested.append(endpoint)
            for project in ['npm-purifier', 'maven-purifier']:
                ci = self.real.asset(next(o['nativeCase']['ciStatus'] for o in self.sidecar['currentObservations'] if o['project'] == project))
                run_id = int(ci['jobs'][0]['url'].split('/actions/runs/')[1].split('/')[0])
                if endpoint.endswith(f'/actions/runs/{run_id}'):
                    return json.dumps({'head_sha': ci['headSha'], 'conclusion':'success', 'status':'completed', 'run_attempt':1})
                for job in ci['jobs']:
                    if endpoint.endswith(f'/actions/jobs/{job["databaseId"]}'):
                        labels = ['ubuntu-24.04-arm'] if 'ubuntu-24.04-arm' in job['name'] else ['ubuntu-latest']
                        return json.dumps({'run_id':run_id, 'head_sha':ci['headSha'], 'conclusion':'success', 'status':'completed', 'run_attempt':1, 'name':job['name'], 'labels':labels})
            raise AssertionError(endpoint)
        with patch('compatibility_reconciliation.subprocess.check_output', side_effect=api):
            self.real.verify_current_ci('npm-purifier')
            self.real.verify_current_ci('maven-purifier')
        self.assertTrue(any('/actions/jobs/' in x for x in requested))

    def test_current_ci_api_rejects_wrong_job_scope_and_missing_job(self):
        o = self.sidecar['currentObservations'][0]
        ci = self.real.asset(o['nativeCase']['ciStatus'])
        run_id = int(ci['jobs'][0]['url'].split('/actions/runs/')[1].split('/')[0])
        for mutation in ['name', 'platform', 'attempt', 'in-progress', 'source']:
            def api(args, **kwargs):
                endpoint = args[-1]
                if '/actions/runs/' in endpoint:
                    return json.dumps({'head_sha': o['sourceRevision'], 'conclusion': 'success', 'status': 'completed', 'run_attempt': 1})
                job_id = int(endpoint.rsplit('/', 1)[-1])
                recorded = next(j for j in ci['jobs'] if j['databaseId'] == job_id)
                result = {'run_id': run_id, 'head_sha': o['sourceRevision'], 'conclusion': 'success', 'status': 'completed', 'name': recorded['name'], 'labels': ['ubuntu-latest'], 'run_attempt': 1}
                result[{'name':'name', 'platform':'labels', 'attempt':'run_attempt', 'in-progress':'status', 'source':'head_sha'}[mutation]] = {'name':'wrong', 'platform':['macos-latest'], 'attempt':2, 'in-progress':'in_progress', 'source':'f'*40}[mutation]
                return json.dumps(result)
            with self.subTest(mutation=mutation), patch('compatibility_reconciliation.subprocess.check_output', side_effect=api), self.assertRaisesRegex(ValueError, 'current native job'):
                self.real.verify_current_ci(o['project'])
        recorded_asset = self.real.asset
        def missing(ref):
            value = recorded_asset(ref)
            if ref == o['nativeCase']['ciStatus']:
                value['jobs'] = [j for j in value['jobs'] if not j['name'].startswith('legacy-native')]
            return value
        with patch.object(self.real, 'asset', side_effect=missing), patch('compatibility_reconciliation.subprocess.check_output', return_value=json.dumps({'head_sha':o['sourceRevision'], 'conclusion':'success', 'status':'completed', 'run_attempt':1})), self.assertRaisesRegex(ValueError, 'job missing'):
            self.real.verify_current_ci(o['project'])

    def test_uv_partial_remains_incomplete(self):
        u = next(x for x in self.data['unresolved'] if x['status'] == PARTIAL)
        u['status'] = CURRENT
        with self.assertRaises(ValueError):
            self.validate(True)

    def test_observed_current_source_inventory_cannot_change(self):
        o = self.sidecar['currentObservations'][0]
        files = self.real.asset(o['sourceTree'])['sourceFiles'].copy()
        files['new-file'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'observed current inputs differ'):
            self.real.classify(o['project'], o['historicalPointId'], o['sourceRevision'], files)

    def test_missing_or_mutated_asset_fails_closed(self):
        reference = self.sidecar['reviewBindings'][0]
        with self.assertRaisesRegex(ValueError, 'missing reconciliation evidence'):
            Reconciliation(self.sidecar, self.registry, self.root)
        target = self.root/reference['path']
        target.parent.mkdir(parents=True)
        target.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'mutated reconciliation evidence'):
            Reconciliation(self.sidecar, self.registry, self.root)

    def test_audit_keeps_raw_drift_and_fails_for_88_plus_partial(self):
        spec = importlib.util.spec_from_file_location('audit_reconciliation_test', ROOT/'tools/audit-compatibility-evidence.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registry = json.loads(self.registry)['projects']
        def observed(project):
            page = next((x for x in self.sidecar['pagesEquivalences'] if x['project'] == project), None)
            if page:
                return page['observedRevision'], self.real.asset(page['reviewBinding'])['newFiles']
            current = next((x for x in self.sidecar['currentObservations'] if x['project'] == project), None)
            if current:
                return current['sourceRevision'], self.real.asset(current['sourceTree'])['sourceFiles']
            unresolved = next((x for x in self.sidecar['unresolved'] if x['project'] == project), None)
            # CMake has two already-matching points at the latest historical review.
            last = registry[project]['reviews'][-1]
            files = copy.deepcopy(last['files'])
            if project == 'sbt-purifier':
                return last['sourceRevision'], files
            if unresolved and project != 'cmake-purifier':
                files['unreviewed-runtime-change'] = '0'*64
            return unresolved['observedRevision'] if unresolved else last['sourceRevision'], files
        def audit(checkout, review, **kwargs):
            revision, files = observed(checkout.name)
            changed = sorted(k for k in set(files) | set(review['files']) if files.get(k) != review['files'].get(k))
            return dict(status='review-needed' if changed else 'inputs-match', currentRevision=revision, testedRevision=review['sourceRevision'], changedFiles=changed)
        import contextlib
        import io
        output = io.StringIO()
        frozen_registry = self.root/'historical-registry.json'
        frozen_registry.write_bytes(self.registry)
        frozen_catalog = self.root/'historical-catalog.json'
        frozen_catalog.write_text(json.dumps({'catalog': self.fixture_catalog}))
        with patch.object(sys, 'argv', ['audit', '--checkouts', '/unused', '--verify-ci', '--registry', str(frozen_registry), '--catalog', str(frozen_catalog)]), patch.object(module, 'inputs', side_effect=lambda checkout, revision: observed(checkout.name)[1]), patch.object(module, 'audit_source', side_effect=audit), patch.object(module, 'verify_ci'), patch.object(Reconciliation, 'verify_current_ci'), contextlib.redirect_stdout(output):
            code = module.main()
        report = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(report['pointCounts'], {MATCH: 9, PAGES: 23, CURRENT: 10, PARTIAL: 1, DRIFT: 88})
        self.assertEqual(report['status'], 'review-needed')
        self.assertFalse(report['nativeTestsExecuted'])
        self.assertEqual(sum(len(p['reviews']) for p in report['projects'].values()), 21)
        self.assertEqual(sum(r['ciEvidence'] == 'verified' for p in report['projects'].values() for r in p['reviews']), 21)
        composer = report['projects']['composer-purifier']
        self.assertEqual(composer['status'], 'review-needed')
        self.assertEqual(composer['currentApplicability'], 'reviewed')
        self.assertEqual(composer['reviews'][0]['changedFiles'], ['.github/workflows/pages.yml'])

    def test_no_source_mode_cannot_claim_current_applicability(self):
        result = subprocess.run([sys.executable, str(ROOT/'tools/audit-compatibility-evidence.py')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['currentApplicability'], 'not-evaluated')
        self.assertEqual(report['pointCounts'], {})
        self.assertFalse(report['nativeTestsExecuted'])


if __name__ == '__main__':
    unittest.main()
