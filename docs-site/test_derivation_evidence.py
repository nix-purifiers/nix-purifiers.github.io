import copy
import unittest
from derivation_evidence import CRITERIA, render_receipts, validate_review


def fixture():
    # Synthetic data tests structural integrity only; never published evidence.
    path = '/nix/store/' + 'a' * 32 + '-sample'
    digest = 'sha256-' + 'A' * 43 + '='
    e = dict(repository='nix-purifiers/example-purifier', revision='a' * 40,
             system='x86_64-linux', check={'kind': 'flake-attribute', 'value': 'checks.x86_64-linux.sample', 'replay': None},
             drvPath=path + '.drv', outputs={'out': path}, outputNarHashes={'out': digest},
             sourceNarHash=digest, sampleSources=[], sdkVersions={'example': '1.2.3'}, build=None)
    e['evaluation'] = dict(sourceRevision=e['revision'], sourceNarHash=digest, check=copy.deepcopy(e['check']), drvPath=e['drvPath'], receipt='https://example.test/artifacts/evaluation.json', artifactSha256='c' * 64)
    e['build'] = dict(status='success', executedSystem=e['system'], sourceRevision=e['revision'],
                      drvPath=e['drvPath'], outputs=copy.deepcopy(e['outputs']),
                      outputNarHashes=copy.deepcopy(e['outputNarHashes']), sourceNarHash=digest,
                      sdkVersions=copy.deepcopy(e['sdkVersions']), sampleSources=[], artifactSha256='b' * 64,
                      receipt='https://example.test/artifacts/build-receipt.json')
    criteria = {key: dict(state='not-met', summary='Inspected the available check; criterion is not demonstrated.',
                         derivations=['sample'], sources=[], gap='Only one SDK and sample have executable coverage.') for key in CRITERIA}
    for key in ('evaluation', 'linux', 'oneVersion'):
        criteria[key].update(state='met', gap=None)
    return {'derivations': {'sample': e}, 'criteria': criteria, 'sampleBuilds': []}


class EvidenceTests(unittest.TestCase):
    def check(self, review):
        return validate_review('nix-purifiers/example-purifier', 'a' * 40, review)

    def test_complete_review_and_conservative_gaps(self):
        self.check(fixture())

    def test_foreign_stale_and_missing_bindings(self):
        for field, value in [('repository', 'other/repo'), ('revision', 'b' * 40),
                             ('drvPath', '/nix/store/not-a-derivation'), ('outputs', {}),
                             ('outputNarHashes', {}), ('sourceNarHash', 'unverified')]:
            with self.subTest(field=field):
                review = fixture()
                review['derivations']['sample'][field] = value
                with self.assertRaises(ValueError):
                    self.check(review)

    def test_build_binding_mismatches(self):
        for field, value in [('sourceRevision', 'b' * 40), ('drvPath', '/different.drv'),
                             ('outputs', {}), ('outputNarHashes', {}),
                             ('sourceNarHash', 'sha256-' + 'B' * 43 + '='),
                             ('sdkVersions', {'example': '9'}), ('receipt', ''), ('artifactSha256', '')]:
            with self.subTest(field=field):
                review = fixture()
                review['derivations']['sample']['build'][field] = value
                with self.assertRaises(ValueError):
                    self.check(review)

    def test_eval_and_cross_execution_cannot_establish_runtime(self):
        for build in (None, dict(fixture()['derivations']['sample']['build'], executedSystem='aarch64-darwin')):
            review = fixture()
            review['derivations']['sample']['build'] = build
            if build is None:
                review['derivations']['sample']['outputNarHashes'] = {}
            with self.assertRaisesRegex(ValueError, 'native build'):
                self.check(review)
            for key in ('linux', 'oneVersion'):
                review['criteria'][key].update(state='not-met', gap='No native build receipt.')
            self.check(review)
            self.assertNotIn('reports native build success', render_receipts(review))

    def test_failed_build_without_realized_outputs_is_honest_gap(self):
        review = fixture()
        e = review['derivations']['sample']
        e['outputNarHashes'] = {}
        e['build'].update(status='failed', outputs={}, outputNarHashes={})
        for key in ('linux', 'oneVersion'):
            review['criteria'][key].update(state='not-met', gap='Build failed before outputs were realized.')
        self.check(review)

    def test_declared_drv_alone_cannot_establish_evaluation(self):
        review = fixture()
        e = review['derivations']['sample']
        e.update(build=None, evaluation=None, outputNarHashes={})
        for key in ('linux', 'oneVersion'):
            review['criteria'][key].update(state='not-met', gap='No successful native build.')
        with self.assertRaisesRegex(ValueError, 'evaluation needs'):
            self.check(review)
        self.assertIn('Declared derivation', render_receipts(review))

    def test_sample_identity_and_native_binding(self):
        review = fixture()
        sample = dict(name='upstream sample', upstream={'repository': 'https://example.test/upstream', 'revision': 'd' * 40, 'sourceNarHash': 'sha256-' + 'D' * 43 + '='}, derivations=['sample'])
        review['sampleBuilds'] = [sample]
        review['derivations']['sample']['sampleSources'] = [copy.deepcopy(sample['upstream'])]
        review['derivations']['sample']['build']['sampleSources'] = [copy.deepcopy(sample['upstream'])]
        self.check(review)
        for field, value in [('derivations', ['missing']), ('upstream', dict(sample['upstream'], revision='e' * 40)), ('upstream', {'repository': 'https://example.test/upstream', 'revision': 'main'})]:
            changed = copy.deepcopy(review)
            changed['sampleBuilds'][0][field] = value
            with self.assertRaises(ValueError):
                self.check(changed)

    def test_unreviewed_missing_gap_and_unknown_refs_rejected(self):
        for field, value in [('state', 'unreviewed'), ('derivations', ['absent']), ('gap', None)]:
            review = fixture()
            review['criteria']['goodTests'][field] = value
            with self.assertRaises(ValueError):
                self.check(review)

    def test_readme_alone_cannot_prove_met(self):
        review = fixture()
        review['criteria']['linux'].update(derivations=[], sources=['https://example.test/README.md'])
        with self.assertRaisesRegex(ValueError, 'executable evidence'):
            self.check(review)

    def test_wrong_os_and_unbound_sdk_rejected(self):
        review = fixture()
        review['criteria']['darwin'].update(state='met', gap=None)
        with self.assertRaisesRegex(ValueError, 'claimed OS'):
            self.check(review)
        review = fixture()
        e = review['derivations']['sample']
        e['sdkVersions'] = e['build']['sdkVersions'] = {}
        with self.assertRaisesRegex(ValueError, 'SDK version'):
            self.check(review)

    def test_rendering_preserves_identity_and_receipt_boundary(self):
        review = fixture()
        self.check(review)
        rendered = render_receipts(review)
        for token in ('Receipt reports native build success', 'checks.x86_64-linux.sample',
                      'a' * 40, '1.2.3', '/nix/store/', 'Build receipt'):
            self.assertIn(token, rendered)
        self.assertNotIn('independently verified', rendered)
        review['derivations']['sample']['check']['value'] = '<script>alert(1)</script>'
        self.assertNotIn('<script>', render_receipts(review))


if __name__ == '__main__':
    unittest.main()
