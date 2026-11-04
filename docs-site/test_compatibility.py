import copy
import json
from pathlib import Path
import unittest

from compatibility import validate, render_compatibility, EMPTY
from content import render, feature_matrix
from reference import reference_text
from export import validate_version_coverage


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent
        self.documentation = json.loads((root / 'catalog.json').read_text())
        self.page = self.documentation['catalog']['npm-purifier']
        self.contract = self.documentation['contract']

    def test_every_overview_and_guide_has_the_same_forced_section(self):
        root = Path(__file__).resolve().parent
        for name, page in self.documentation['catalog'].items():
            with self.subTest(name=name):
                overview = render(page, self.contract)[0]
                guide = reference_text(page['repository'], (root / 'references' / (name + '.md')).read_text(), page)
                body = render_compatibility(page, self.contract)
                self.assertIn(body, overview)
                self.assertIn(body, guide)
                self.assertEqual(overview.count('## Version compatibility\n'), 1)
                self.assertIn('[Version compatibility](./#version-compatibility)', feature_matrix(page, self.contract))

    def test_unknown_versions_are_explicit_without_inventing_a_floor(self):
        page = dict(self.page, compatibility=copy.deepcopy(EMPTY))
        body = render_compatibility(page, self.contract)
        self.assertIn('have not yet been recorded', body)
        self.assertNotIn('>=', body)

    def test_tested_roles_remain_distinct_and_do_not_create_a_range(self):
        body = render_compatibility(self.page, self.contract)
        self.assertIn('Build tool / package manager: npm 6.14.16', body)
        self.assertIn('Project runtime: Node.js 12.22.12', body)
        self.assertIn('Capture / build helper: Node.js 24.21.0', body)
        self.assertIn('x86_64-linux', body)
        self.assertNotIn('aarch64-linux', body.split('### Tested combinations', 1)[1])
        self.assertIn('packaged defaults do not establish a minimum version', body)
        self.assertIn('do not establish a minimum version', body)

    def test_every_published_page_has_real_versions_or_a_project_selection(self):
        validate_version_coverage(self.documentation['catalog'])
        for name, page in self.documentation['catalog'].items():
            with self.subTest(name=name):
                self.assertTrue(page['compatibility']['defaults'])
                self.assertNotIn('have not yet been recorded for this purifier', render_compatibility(page, self.contract))
                for item in page['compatibility']['defaults']:
                    self.assertTrue(item['systems'])
                    self.assertEqual(len(item['sourceRevision']), 40)

    def test_empty_framework_cannot_be_published(self):
        page = dict(self.page, compatibility=copy.deepcopy(EMPTY))
        with self.assertRaises(ValueError):validate_version_coverage({'npm-purifier': page})

    def test_gradle_is_project_selected_instead_of_a_fictitious_bundled_version(self):
        page = self.documentation['catalog']['gradle-purifier']
        self.assertFalse(any(x['name'] == 'Gradle' for x in page['compatibility']['defaults']))
        choice = next(x for x in page['compatibility']['projectSelections'] if x['name'] == 'Gradle')
        self.assertIn('gradle/wrapper/gradle-wrapper.properties', choice['inputs'])
        self.assertIn('Java 17', ' '.join(x['text'] for x in page['compatibility']['limitations']))

    def test_quickstart_zig_selection_is_distinct_from_the_default(self):
        rows = self.documentation['catalog']['zig-purifier']['compatibility']['defaults']
        quickstart = [x for x in rows if 'Quickstart' in x['selection']]
        self.assertTrue(quickstart)
        self.assertTrue(all(x['version'].startswith('0.15.') for x in quickstart))
        self.assertTrue(any(x['selection'] == 'default' and x['version'] != quickstart[0]['version'] for x in rows if x['name'] == 'Zig'))

    def test_tested_points_require_exact_versions_scope_and_evidence(self):
        for change in ['range-as-version', 'missing-evidence', 'missing-scope', 'duplicate-component']:
            data = copy.deepcopy(self.page['compatibility'])
            point = data['testedPoints'][0]
            if change == 'range-as-version':point['components'][0]['version'] = '>=6'
            elif change == 'missing-evidence':point['evidence'] = []
            elif change == 'missing-scope':point['operations'] = []
            else:point['components'].append(point['components'][0])
            with self.subTest(change=change), self.assertRaises(ValueError):validate(data)

    def test_range_requires_a_review_and_known_supporting_test(self):
        data = copy.deepcopy(self.page['compatibility'])
        point = data['testedPoints'][0]
        claim = dict(role='native-tool', name='npm', range='6.x', systems=['x86_64-linux'],
                     operations=['pure-build'], sourceRevision=point['sourceRevision'],
                     evidence=point['evidence'], basis='Explicit resolver compatibility review.',
                     supportingTests=['absent'])
        data['supportedRanges'] = [claim]
        with self.assertRaises(ValueError):validate(data)
        claim['supportingTests'] = [point['id']]
        validate(data)
        del claim['basis']
        with self.assertRaises(ValueError):validate(data)


if __name__ == '__main__':unittest.main()
