import copy
import hashlib
import gzip
import io
import json
from pathlib import Path
import tempfile
import subprocess
import tarfile
import unittest

from compatibility import validate, EMPTY
from compatibility_evidence import (input_digest, publication_inputs_1f49,
    validate_runtime_publication, publication_archive_fingerprint, inputs, PINNED_PUBLICATION_SCRIPT_SHA256)

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
            ('policySource', 'releaseManifest', 'runtimeArchive', 'releaseChecksums',
             'publicationRun', 'publicationJobs', 'publicationLog')]
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

    def update_checksums(self):
        def digest(key):
            return hashlib.sha256((self.directory / self.proof[key].rsplit('/', 1)[1]).read_bytes()).hexdigest()
        raw = (digest('releaseManifest') + '  release-manifest.json\n'
               + digest('runtimeArchive') + '  source.tar.gz\n').encode('ascii')
        self.proof['releaseChecksums'] = self.retain(raw, 'txt')

    def changed_archive(self, mutation):
        raw = (self.directory / self.proof['runtimeArchive'].rsplit('/', 1)[1]).read_bytes()
        output = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as original, \
                tarfile.open(fileobj=output, mode='w:gz') as changed:
            for member in original:
                member = copy.copy(member)
                body = original.extractfile(member).read() if member.isfile() else None
                if member.name == 'swiftpm-purifier/LICENSE':
                    if mutation == 'missing':
                        continue
                    if mutation == 'body':
                        body += b'changed\n'
                        member.size = len(body)
                    elif mutation == 'mode':
                        member.mode ^= 0o111
                    elif mutation == 'hardlink':
                        member.type, member.linkname, member.size, body = tarfile.LNKTYPE, 'LICENSE', 0, None
                    elif mutation == 'duplicate':
                        changed.addfile(member, io.BytesIO(body))
                changed.addfile(member, io.BytesIO(body) if body is not None else None)
            if mutation in ('extra', 'traversal'):
                member = tarfile.TarInfo('swiftpm-purifier/extra' if mutation == 'extra' else '../escape')
                member.size = 3
                changed.addfile(member, io.BytesIO(b'bad'))
        self.proof['runtimeArchive'] = self.retain(output.getvalue(), 'bin')
        self.update_checksums()

    def test_coherent_wrong_proof_manifest_and_checksums_fingerprint_is_rejected(self):
        self.proof['runtimeFingerprint'] = 'f'*64
        self.change_record('releaseManifest', lambda record: record.update(fingerprint='f'*64))
        self.update_checksums()
        with self.assertRaisesRegex(ValueError, 'recomputed runtime fingerprint differs'):
            self.check()

    def test_modified_archive_body_or_mode_with_coherent_checksums_is_rejected(self):
        original = copy.deepcopy(self.proof)
        for mutation in ('body', 'mode'):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'complete reviewed runtime inventory'):
                self.proof = copy.deepcopy(original)
                self.changed_archive(mutation)
                self.check()

    def test_archive_rejects_missing_extra_duplicate_unsafe_and_hardlinked_files(self):
        original = copy.deepcopy(self.proof)
        for mutation in ('missing', 'extra', 'duplicate', 'traversal', 'hardlink'):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'archive'):
                self.proof = copy.deepcopy(original)
                self.changed_archive(mutation)
                self.check()

    def test_manifest_and_archive_are_bound_to_retained_release_checksums(self):
        self.proof['releaseChecksums'] = self.retain(
            ('0'*64 + '  release-manifest.json\n' + '0'*64 + '  source.tar.gz\n').encode(), 'txt')
        with self.assertRaisesRegex(ValueError, 'checksum differs'):
            self.check()

    def test_archive_git_identity_matches_git_for_symlinks_executables_and_path_order(self):
        checkout = self.directory / 'git-reference'
        checkout.mkdir()
        subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
        bodies = {'README.md': b'ignored by historical policy\n', 'a.bar': b'first\n',
                  'a/file': b'nested\n', 'sub/run': b'#!/bin/sh\nexit 0\n', 'sub/λ.txt': b'utf8 path\n'}
        for name, raw in bodies.items():
            path = checkout / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (checkout / 'sub/run').chmod(0o755)
        (checkout / 'current').symlink_to('sub/run')
        subprocess.run(['git', '-C', str(checkout), '-c', 'core.autocrlf=false',
                        '-c', 'core.filemode=true', 'add', '--all'], check=True)
        tree = subprocess.check_output(['git', '-C', str(checkout), 'write-tree'], text=True).strip()
        raw = subprocess.check_output(['git', '-C', str(checkout), 'archive', '--format=tar', '--prefix=demo/', tree])
        reviewed = inputs(checkout, tree)
        actual = publication_archive_fingerprint(gzip.compress(raw, mtime=0), reviewed, 'example/demo')
        wanted = {'a.bar', 'a/file', 'sub/run', 'sub/λ.txt', 'current'}
        entries = subprocess.check_output(['git', '-C', str(checkout), 'ls-tree', '-r', '-z', tree]).split(b'\0')
        selected = [entry for entry in entries if entry and entry.split(b'\t', 1)[1].decode() in wanted]
        self.assertEqual(actual, hashlib.sha256(b'\0'.join(selected)).hexdigest())

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
