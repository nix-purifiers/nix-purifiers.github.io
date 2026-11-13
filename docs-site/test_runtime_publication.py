import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from compatibility import validate, EMPTY
from compatibility_evidence import (input_digest, publication_inputs_1f49,
    validate_runtime_publication, PINNED_PUBLICATION_SCRIPT_SHA256)

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = 'https://nix-purifiers.github.io/evidence/'


class RuntimePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        registry = json.loads((ROOT / 'model/compatibility-tests.json').read_text())
        self.entry = copy.deepcopy(registry['projects']['swiftpm-purifier'])
        self.point = copy.deepcopy(next(p for p in self.entry['testedPoints']
            if p['id'] == 'swift-5.0.3-swiftpm-5.0.0-local-fixture-linux-48aed73'))
        self.repository = 'nix-purifiers/swiftpm-purifier'
        self.proof = self.read_original(self.point['runtimePublication']['proof'])
        urls = [self.point['runtimePublication']['proof']] + [self.proof[k] for k in
            ('policySource', 'releaseManifest', 'publicationRun', 'publicationJobs', 'publicationLog')]
        for url in urls:
            name = url.rsplit('/', 1)[1]
            (self.directory / name).write_bytes((ROOT / 'docs-site/evidence' / name).read_bytes())

    def read_original(self, url):
        return json.loads((ROOT / 'docs-site/evidence' / url.rsplit('/', 1)[1]).read_bytes())

    def retain(self, value, extension='json'):
        raw = (json.dumps(value, indent=2) + '\n').encode() if extension == 'json' else value
        name = hashlib.sha256(raw).hexdigest() + '.' + extension
        (self.directory / name).write_bytes(raw)
        return PUBLIC + name

    def check(self):
        self.point['runtimePublication']['proof'] = self.retain(self.proof)
        validate_runtime_publication(self.point, self.entry, self.repository, self.directory)

    def change_record(self, key, mutation):
        value = self.read_original(self.proof[key])
        mutation(value)
        self.proof[key] = self.retain(value)

    def test_actual_dual_provenance_is_valid_without_relabeling_tested_source(self):
        self.check()
        self.assertNotEqual(self.point['sourceRevision'], self.point['runtimePublication']['sourceRevision'])
        self.assertEqual(len(self.proof['equivalentInputs']), 95)

    def test_complete_policy_matches_actual_pinned_fingerprint_selection(self):
        script = (self.directory / self.proof['policySource'].rsplit('/', 1)[1]).read_bytes()
        self.assertEqual(hashlib.sha256(script).hexdigest(), PINNED_PUBLICATION_SCRIPT_SHA256)
        closure_url = next(url for url in self.point['evidence'] if url.endswith('.json')
                           and self.read_original(url).get('pinnedInfrastructure'))
        closure = self.read_original(closure_url)
        selected = closure['eligibleReleasedRuntimeJoins']
        for revision in (self.point['sourceRevision'], self.point['runtimePublication']['sourceRevision']):
            review = next(r for r in self.entry['reviews'] if r['sourceRevision'] == revision)
            self.assertEqual(set(publication_inputs_1f49(review['files'])), set(selected))
        rows = [f"{selected[p]['gitMode']} blob {selected[p]['blob']}\t{p}".encode() for p in sorted(selected)]
        digest = hashlib.sha256(b'\0'.join(rows)).hexdigest()
        self.assertEqual(set(closure['recomputedFingerprints'].values()), {digest})
        self.assertEqual(self.read_original(self.proof['releaseManifest'])['fingerprint'], digest)

    def test_historical_policy_does_not_inherit_new_exported_fixture_exceptions(self):
        paths = {p: 'digest' for p in ['tests/python/native_composition.py', 'tests/x', 'docs/x',
            '.github/x', 'README.md', '.gitignore', 'pkgs/tests.py', 'tests-tools/x', 'README.md.in']}
        self.assertEqual(set(publication_inputs_1f49(paths)), {'pkgs/tests.py', 'tests-tools/x', 'README.md.in'})

    def test_proof_rejects_missing_or_extra_eligible_inputs(self):
        original = copy.deepcopy(self.proof)
        for extra in (False, True):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'complete publisher input'):
                self.proof = copy.deepcopy(original)
                if extra:
                    self.proof['equivalentInputs']['pkgs/invented.py'] = '0'*64
                else:
                    del self.proof['equivalentInputs'][next(iter(self.proof['equivalentInputs']))]
                self.check()

    def test_production_file_change_cannot_be_hidden_by_updating_inventory_digest(self):
        tested = next(r for r in self.entry['reviews'] if r['sourceRevision'] == self.point['sourceRevision'])
        path = next(iter(self.proof['equivalentInputs']))
        tested['files'][path] = 'f'*64
        self.proof['testedInputDigest'] = input_digest(tested['files'])
        with self.assertRaisesRegex(ValueError, 'complete publisher input'):
            self.check()

    def test_extra_runtime_path_cannot_be_ignored(self):
        tested = next(r for r in self.entry['reviews'] if r['sourceRevision'] == self.point['sourceRevision'])
        tested['files']['pkgs/new-runtime.py'] = 'f'*64
        self.proof['testedInputDigest'] = input_digest(tested['files'])
        with self.assertRaisesRegex(ValueError, 'complete publisher input'):
            self.check()

    def test_mode_aware_runtime_hash_change_is_rejected(self):
        self.proof['equivalentInputs'][next(iter(self.proof['equivalentInputs']))] = 'e'*64
        with self.assertRaisesRegex(ValueError, 'complete publisher input'):
            self.check()

    def test_wrong_manifest_version_source_or_kind_is_rejected(self):
        original = copy.deepcopy(self.proof)
        for key, value in [('version', '0.1.11'), ('commit', self.point['sourceRevision']), ('kind', 'python'), ('fingerprint', 'f'*64)]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'wrong released manifest'):
                self.proof = copy.deepcopy(original)
                self.change_record('releaseManifest', lambda record: record.update({key: value}))
                self.check()

    def test_wrong_proof_identity_or_unknown_fields_are_rejected(self):
        original = copy.deepcopy(self.proof)
        mutations = [('testedSourceRevision', 'a'*40), ('runtimeSourceRevision', 'b'*40),
                     ('releasedVersion', '0.1.11'), ('unknown', True), ('repository', 'other/repo')]
        for key, value in mutations:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.proof = copy.deepcopy(original)
                self.proof[key] = value
                self.check()

    def test_unknown_policy_or_changed_pinned_script_is_rejected(self):
        original = copy.deepcopy(self.proof)
        self.proof['policyRevision'] = 'a'*40
        with self.assertRaisesRegex(ValueError, 'unknown publisher policy'):
            self.check()
        self.proof = original
        self.proof['policySource'] = self.retain(b'changed policy\n', 'txt')
        with self.assertRaisesRegex(ValueError, 'wrong pinned publisher script'):
            self.check()

    def test_new_archive_claim_or_non_noop_is_rejected(self):
        original = copy.deepcopy(self.proof)
        for key, value in [('publication', 'release'), ('newSourceArchivePublished', True)]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'unchanged runtime'):
                self.proof = copy.deepcopy(original)
                self.proof[key] = value
                self.check()

    def test_wrong_run_or_job_source_is_rejected(self):
        original = copy.deepcopy(self.proof)
        self.change_record('publicationRun', lambda record: record.update(head_sha='a'*40))
        with self.assertRaisesRegex(ValueError, 'wrong publisher run'):
            self.check()
        self.proof = original
        self.change_record('publicationJobs', lambda record: record['jobs'][0].update(head_sha='a'*40))
        with self.assertRaisesRegex(ValueError, 'wrong publisher job'):
            self.check()

    def test_publisher_run_must_reference_the_exact_historical_workflow(self):
        self.change_record('publicationRun', lambda record: record.update(referenced_workflows=[]))
        with self.assertRaisesRegex(ValueError, 'pinned policy'):
            self.check()

    def test_skipped_or_failed_publisher_step_is_rejected(self):
        original = copy.deepcopy(self.proof)
        for conclusion in ('skipped', 'failure'):
            with self.subTest(conclusion=conclusion), self.assertRaisesRegex(ValueError, 'did not execute'):
                self.proof = copy.deepcopy(original)
                def change(record):
                    next(s for s in record['jobs'][0]['steps'] if s['number'] == 5)['conclusion'] = conclusion
                self.change_record('publicationJobs', change)
                self.check()

    def test_missing_or_outside_step_noop_message_is_rejected(self):
        original = copy.deepcopy(self.proof)
        for raw in (b'no publication output\n',
                    b'2000-01-01T00:00:00Z The latest release already contains these sources and locked dependencies.\n'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'no executed NOOP|checkout and invocation'):
                self.proof = copy.deepcopy(original)
                self.proof['publicationLog'] = self.retain(raw, 'log')
                self.check()

    def test_missing_corrupt_or_unretained_proof_is_rejected(self):
        url = self.point['runtimePublication']['proof']
        path = self.directory / url.rsplit('/', 1)[1]
        path.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            validate_runtime_publication(self.point, self.entry, self.repository, self.directory)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            validate_runtime_publication(self.point, self.entry, self.repository, self.directory)
        self.point['runtimePublication']['proof'] = 'https://example.test/proof.json'
        with self.assertRaisesRegex(ValueError, 'content-addressed'):
            validate_runtime_publication(self.point, self.entry, self.repository, self.directory)

    def test_optional_point_object_remains_exactly_typed(self):
        original = copy.deepcopy(self.point)
        for publication in (None, {}, dict(original['runtimePublication'], extra='unexpected'),
                            dict(original['runtimePublication'], version='a'*40),
                            dict(original['runtimePublication'], version=1),
                            dict(original['runtimePublication'], sourceRevision=None),
                            dict(original['runtimePublication'], proof=[])):
            with self.subTest(publication=publication), self.assertRaises(ValueError):
                point = dict(original, runtimePublication=publication)
                validate(dict(EMPTY, testedPoints=[point]))
