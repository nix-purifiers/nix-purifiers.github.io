"""Coverage obligations must expose missing contexts without claiming support."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('nix'), 'Nix evaluates the behavior catalog')
class CoveragePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        def evaluate(attribute):
            return json.loads(subprocess.check_output(
                ['nix', 'eval', '--json', '.#' + attribute], cwd=cls.root, text=True))
        cls.plan = evaluate('coveragePlan')
        cls.catalog = evaluate('catalog')

    def test_every_modeled_project_has_explicit_unexecuted_obligations(self):
        self.assertEqual(set(self.catalog), set(self.plan['projects']))
        for project in self.plan['projects'].values():
            obligations = project['obligations']
            self.assertEqual(len(obligations), len({case['id'] for case in obligations}))
            self.assertTrue(all(case['execution'] == 'not-run' for case in obligations))
            self.assertEqual(project['sdkMatrix']['state'], 'needs-review')

    def test_lifecycle_and_both_adopter_sandwiches_are_independent(self):
        cases = {case['id']: case for case in self.plan['projects']['uv-purifier']['obligations']}
        self.assertTrue({'lifecycle.dependency-bump', 'lifecycle.dependency-add',
                         'lifecycle.dependency-drop', 'lifecycle.native-to-nix',
                         'lifecycle.nix-to-native', 'lifecycle.buildable-add',
                         'lifecycle.buildable-drop', 'sandwich.purifier-ordinary-purifier',
                         'sandwich.ordinary-purifier-ordinary'} <= set(cases))
        self.assertEqual(cases['lifecycle.buildable-add']['applicability'], 'needs-review')
        self.assertIn('no-purifier-integration', cases['projection.outgoing-ordinary']['observations'])
        self.assertIn('downstream-own-eviction', cases['graph.republication-evictions']['observations'])
        self.assertEqual(cases['resolver.maven-managed-override']['applicability'], 'not-applicable')
        maven = {case['id']: case for case in self.plan['projects']['maven-purifier']['obligations']}
        constraints = maven['resolver.maven-managed-override']
        self.assertEqual(constraints['applicability'], 'required')
        self.assertTrue({'soft-request-preserves-nix', 'incompatible-hard-request-rejected',
                         'explicit-exclusion-origin-loss-detected'} <= set(constraints['observations']))

    def test_candidates_are_directional_and_preserve_interface_and_conditions(self):
        pairs = {(edge['producer'], edge['consumer']) for edge in self.plan['projectionCandidates']}
        self.assertIn(('maven-purifier', 'gradle-purifier'), pairs)
        self.assertIn(('gradle-purifier', 'maven-purifier'), pairs)
        for edge in self.plan['projectionCandidates']:
            producer, consumer = self.catalog[edge['producer']], self.catalog[edge['consumer']]
            self.assertEqual(edge['status'], 'candidate')
            self.assertEqual(edge['execution'], 'not-run')
            self.assertIn(edge['format'], producer['facts']['projection_outgoing_formats']['value'])
            self.assertIn(edge['format'], consumer['facts']['projection_incoming_formats']['value'])
            self.assertIn(edge['outgoingInterface'], producer['facts']['projection_outgoing_interfaces']['value'])
            self.assertIn(edge['incomingInterface'], consumer['facts']['projection_incoming_interfaces']['value'])
            self.assertEqual(set(edge['systems']), set(producer['facts']['platforms']['value'])
                             & set(consumer['facts']['platforms']['value']))

    def test_unknown_and_unsupported_projections_never_generate_a_supported_claim(self):
        for name, model in self.catalog.items():
            cases = {case['id']: case for case in self.plan['projects'][name]['obligations']}
            for direction, case in [('incoming', 'projection.incoming'),
                                    ('outgoing', 'projection.outgoing-ordinary')]:
                fact = model['facts']['projection_' + direction]
                expected = ('needs-review' if fact['state'] != 'known' else
                            'not-applicable' if fact['value'] == 'unsupported' else 'required')
                self.assertEqual(cases[case]['applicability'], expected)


if __name__ == '__main__':
    unittest.main()
