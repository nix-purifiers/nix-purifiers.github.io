"""Retained Cabal plan drift must fail before a site is written."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build import build
from testing import canonical_coverage_plan, catalog_digest


class CoverageBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent
        cls.fixture = json.loads((cls.root / 'fixtures/stale-coverage-plan-cabal.json').read_text())

    def document(self, snapshot='after'):
        retained = copy.deepcopy(self.fixture[snapshot])
        return {'catalog': retained['catalog'], 'contract': {}, 'coveragePlan': {
            'version': 1, 'scope': 'coverage-obligations',
            'catalogDigest': retained['catalogDigest'],
            'projects': {'cabal-purifier': retained['project']},
            'projectionCandidates': [],
        }}

    def test_retained_nix_digests_match_python_without_recomputing_the_oracle(self):
        for snapshot in ('before', 'after'):
            with self.subTest(snapshot=snapshot):
                retained = self.fixture[snapshot]
                self.assertEqual(catalog_digest(retained['catalog']), retained['catalogDigest'])
                canonical_coverage_plan(self.document(snapshot))

    def test_retained_old_plan_cannot_override_current_export_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'site'
            with self.assertRaisesRegex(ValueError, 'differs from the canonical export'):
                build(self.document(), output, coverage_plan=self.document('before')['coveragePlan'])
            self.assertFalse(output.exists())

    def test_retained_stale_embedded_plan_is_rejected(self):
        documentation = self.document()
        documentation['coveragePlan'] = self.document('before')['coveragePlan']
        with self.assertRaisesRegex(ValueError, 'does not match the exported catalog facts'):
            canonical_coverage_plan(documentation)

    def test_fact_or_invocation_changes_at_the_same_revision_invalidate_the_plan(self):
        for mutation in ('fact', 'operation'):
            with self.subTest(mutation=mutation):
                documentation = self.document()
                page = documentation['catalog']['cabal-purifier']
                revision = page['reviewedRevision']
                if mutation == 'fact':
                    page['facts']['projection_outgoing']['value'] = 'unsupported'
                else:
                    page['operations']['lock']['arguments'].append('--different-invocation')
                self.assertEqual(page['reviewedRevision'], revision)
                with self.assertRaisesRegex(ValueError, 'does not match the exported catalog facts'):
                    canonical_coverage_plan(documentation)

    def test_matching_external_plan_is_allowed_but_modified_obligations_are_not(self):
        documentation = self.document()
        supplied = copy.deepcopy(documentation['coveragePlan'])
        self.assertEqual(canonical_coverage_plan(documentation, supplied), documentation['coveragePlan'])
        supplied['projects']['cabal-purifier']['obligations'][0]['applicability'] = 'not-applicable'
        with self.assertRaisesRegex(ValueError, 'differs from the canonical export'):
            canonical_coverage_plan(documentation, supplied)

    def test_missing_plan_and_inconsistent_project_identity_are_rejected(self):
        documentation = self.document()
        documentation.pop('coveragePlan')
        with self.assertRaisesRegex(ValueError, 'regenerate .#documentation'):
            canonical_coverage_plan(documentation)
        for field, value in [('repository', 'nix-purifiers/another-purifier'),
                             ('reviewedRevision', '0' * 40), ('systems', ['aarch64-windows'])]:
            with self.subTest(field=field):
                documentation = self.document()
                documentation['coveragePlan']['projects']['cabal-purifier'][field] = value
                with self.assertRaisesRegex(ValueError, 'identity or platforms'):
                    canonical_coverage_plan(documentation)

    def test_stale_audit_and_plan_rejection_preserve_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            marker = output / 'existing.txt'
            marker.write_text('preserve existing site')
            with self.assertRaisesRegex(ValueError, 'Coverage evidence is stale'):
                build(self.document(), output, coverage_audit={'planDigest': 'stale'})
            self.assertEqual(list(output.iterdir()), [marker])
            self.assertEqual(marker.read_text(), 'preserve existing site')

    def test_cli_rejects_retained_stale_plan_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export = root / 'export.json'
            stale = root / 'stale.json'
            export.write_text(json.dumps(self.document()))
            stale.write_text(json.dumps(self.document('before')['coveragePlan']))
            output = root / 'site'
            result = subprocess.run([sys.executable, str(self.root / 'build.py'),
                                     '--export', str(export), '--coverage-plan', str(stale),
                                     '--output', str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('differs from the canonical export', result.stderr)
            self.assertFalse(output.exists())

    def test_malformed_nested_plan_or_audit_preserves_existing_site(self):
        for malformed in ('missing-plan-cases', 'missing-context-cases', 'bad-observation-map',
                          'invalid-utf8', 'unsafe-name'):
            with self.subTest(malformed=malformed), tempfile.TemporaryDirectory() as directory:
                documentation = self.document()
                plan = documentation['coveragePlan']
                evidence = None
                if malformed == 'missing-plan-cases':
                    plan['projects']['cabal-purifier'].pop('obligations')
                elif malformed == 'unsafe-name':
                    name = '../outside'
                    documentation['catalog'][name] = documentation['catalog'].pop('cabal-purifier')
                    plan['projects'][name] = plan['projects'].pop('cabal-purifier')
                    plan['catalogDigest'] = catalog_digest(documentation['catalog'])
                else:
                    context = ({} if malformed == 'missing-context-cases' else
                               {'obligations': {}, 'source': '\ud800'} if malformed == 'invalid-utf8' else
                               {'obligations': {'case': []}})
                    digest = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                    evidence = {'planDigest': digest, 'projects': {'cabal-purifier': {'contexts': [context]}}}
                output = Path(directory) / 'site'
                output.mkdir()
                marker = output / 'existing.txt'
                marker.write_text('preserve existing site')
                with self.assertRaises((KeyError, TypeError, AttributeError, ValueError)):
                    build(documentation, output, coverage_audit=evidence)
                self.assertEqual(list(output.iterdir()), [marker])
                self.assertEqual(marker.read_text(), 'preserve existing site')
