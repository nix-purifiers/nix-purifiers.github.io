import copy
import unittest

from coverage import audit, digest


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.project = {'systems': ['x86_64-linux'], 'cacheProfiles': ['cold', 'warm'],
                        'sdkMatrix': {'state': 'needs-review'}, 'obligations': [
                            {'id': 'sandwich', 'applicability': 'required',
                             'observations': ['eviction', 'execution']} ]}
        self.plan = {'projects': {'maven': self.project}, 'projectionCandidates': []}
        self.target = dict(system='x86_64-linux', nativeSDK='maven-jdk', cacheProfile='cold',
                           sourceNarHash='sha256-source', sourceRevision='revision', inputsDigest='inputs',
                           driverDigest='driver', graphHelperDigest='helper')
        self.entry = {'provenance': dict(self.target, planDigest=digest(self.project)),
                      'observations': {'sandwich': {'eviction': {'status': 'passed'},
                                                   'execution': {'status': 'passed'}}}}

    def run_audit(self, entries=None, targets=None):
        return audit(self.plan, {'maven': [self.entry] if entries is None else entries},
                     {'maven': [self.target] if targets is None else targets})

    def context(self, **kwargs):
        return self.run_audit(**kwargs)['projects']['maven']['contexts'][0]

    def test_observed_context_can_pass_while_sdk_matrix_is_unreviewed(self):
        result = self.run_audit()
        self.assertTrue(result['projects']['maven']['contexts'][0]['complete'])
        self.assertFalse(result['projects']['maven']['complete'])
        self.assertFalse(result['complete'])

    def test_overall_runner_success_cannot_fill_missing_observations(self):
        self.entry['selectedCasesPassed'] = True
        del self.entry['observations']['sandwich']['eviction']
        result = self.context()
        self.assertFalse(result['complete'])
        self.assertEqual(result['obligations']['sandwich']['eviction'], 'not-run')

    def test_each_independent_provenance_field_invalidates_success(self):
        for field in self.target:
            with self.subTest(field=field):
                entry = copy.deepcopy(self.entry)
                entry['provenance'][field] = 'different'
                self.assertFalse(self.context(entries=[entry])['complete'])

    def test_warm_and_cold_contexts_cannot_share_a_pass(self):
        warm = dict(self.target, cacheProfile='warm')
        result = self.run_audit(targets=[self.target, warm])['projects']['maven']['contexts']
        self.assertTrue(result[0]['complete'])
        self.assertFalse(result[1]['complete'])

    def test_changed_plan_and_unknown_observations_are_rejected(self):
        self.project['obligations'][0]['observations'].append('origin')
        self.assertFalse(self.context()['complete'])
        self.entry['observations']['sandwich']['typo'] = {'status': 'passed'}
        self.assertTrue(self.context()['problems'])

    def test_duplicate_evidence_and_empty_targets_do_not_pass(self):
        self.assertFalse(self.context(entries=[self.entry, self.entry])['complete'])
        self.assertFalse(self.run_audit(targets=[])['projects']['maven']['complete'])

    def test_reviewed_sdk_does_not_hide_missing_system_or_cache_contexts(self):
        self.project['sdkMatrix'] = {'state': 'reviewed', 'profiles': ['maven-jdk']}
        self.project['systems'].append('aarch64-linux')
        self.entry['provenance']['planDigest'] = digest(self.project)
        project = self.run_audit()['projects']['maven']
        self.assertTrue(project['contexts'][0]['complete'])
        self.assertFalse(project['complete'])
        self.assertEqual(len(project['missingMatrixContexts']), 3)


if __name__ == '__main__':
    unittest.main()
