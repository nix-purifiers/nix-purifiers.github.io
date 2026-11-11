import copy
import json
import re
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

    def test_sbt_implementation_selection_extends_existing_version_selections(self):
        root = Path(__file__).resolve().parents[1]
        requirements = json.loads((root / 'model/version-requirements.json').read_text())
        selections = requirements['projects']['sbt-purifier']['projectSelections']
        existing = [item for item in self.documentation['catalog']['sbt-purifier']['compatibility']['projectSelections']
                    if item['role'] != 'purifier-implementation']
        self.assertEqual(selections[:-1], existing)
        self.assertEqual(selections[-1]['role'], 'purifier-implementation')
        self.assertEqual(selections[-1]['inputs'], ['sbt-purifier.lock.json', 'implementation.source'])
        page = copy.deepcopy(self.documentation['catalog']['sbt-purifier'])
        page['compatibility']['projectSelections'] = selections
        validate(page['compatibility'])
        body = render_compatibility(page, self.contract)
        self.assertIn('Purifier implementation: sbt-purifier', body)
        self.assertIn('project/build.properties', body)
        self.assertIn('self-update', body)
        bad = copy.deepcopy(page['compatibility'])
        bad['projectSelections'][-1]['role'] = 'arbitrary-implementation'
        with self.assertRaises(ValueError):
            validate(bad)

    def test_nix_scope_selection_renders_actual_attributes_without_file_links(self):
        page = copy.deepcopy(self.documentation['catalog']['ant-purifier'])
        selections = page['compatibility']['projectSelections']
        self.assertTrue(selections)
        self.assertTrue(all(item['kind'] == 'nix-scope' for item in selections))
        self.assertEqual({name for item in selections for name in item['inputs']},
                         {'nativeProfile', 'legacyJvmAdapter', 'ant', 'apacheIvy'})
        body = render_compatibility(page, self.contract)
        self.assertIn('Nix scope configuration: `nativeProfile`, `ant`', body)
        self.assertIn('Nix scope configuration: `legacyJvmAdapter`', body)
        self.assertNotIn('[legacyJvmAdapter](', body)
        self.assertNotIn('[nativeProfile](', body)

    def test_selection_kinds_remain_closed_and_existing_kinds_keep_their_rendering(self):
        for kind in ['project-file', 'environment', 'lockfile', 'command-option', 'nix-scope']:
            data = copy.deepcopy(EMPTY)
            data['projectSelections'] = [dict(role='compiler', name='JDK', kind=kind,
                inputs=['actualInput'], description='Actual selection mechanism.',
                sourceRevision='1'*40, evidence=['https://example.test/definition'])]
            with self.subTest(kind=kind):
                self.assertEqual(validate(data)['projectSelections'][0]['kind'], kind)
                body = render_compatibility(dict(self.page, compatibility=data), self.contract)
                self.assertIn('`actualInput`', body)
                self.assertEqual('Nix scope configuration:' in body, kind == 'nix-scope')
            data['projectSelections'][0]['kind'] = 'guessed-kind'
            with self.assertRaises(ValueError):
                validate(data)
            data['projectSelections'][0]['kind'] = kind
            data['projectSelections'][0]['inputs'] = []
            with self.assertRaises(ValueError):
                validate(data)

    def test_ant_legacy_point_keeps_class_tree_and_native_publication_distinct(self):
        page = self.documentation['catalog']['ant-purifier']
        point = page['compatibility']['testedPoints'][0]
        self.assertEqual(point['system'], 'x86_64-linux')
        self.assertEqual({(c['role'], c['name']): c['version'] for c in point['components']}, {
            ('native-tool', 'Apache Ant'): '1.5.4', ('native-tool', 'Apache Ivy'): '2.4.0',
            ('native-tool-runtime', 'Azul Zulu JDK'): '6.0.119',
            ('compiler', 'Azul Zulu JDK'): '6.0.119',
            ('project-runtime', 'Azul Zulu JDK'): '6.0.119'})
        self.assertFalse({'native-publish', 'release-pack', 'pure-native-byte-equality',
                          'native-published-class-byte-equality'} & set(point['operations']))
        self.assertFalse(page['compatibility']['supportedRanges'])
        notes = ' '.join(point['notes'])
        self.assertIn('source/class-tree archive, not native artifact publication fidelity', notes)
        self.assertIn('compiled Main.class bytes match the independent native control', notes)
        self.assertIn('not a JUnit task', notes)
        self.assertIn('Arbitrary custom-task introspection is not established', notes)

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
                self.assertIn('[Version compatibility](reference.html#version-compatibility)', feature_matrix(page, self.contract))

    def test_unknown_versions_are_explicit_without_inventing_a_floor(self):
        page = dict(self.page, compatibility=copy.deepcopy(EMPTY))
        body = render_compatibility(page, self.contract)
        self.assertIn('Version information has not been recorded.', body)
        self.assertNotIn('>=', body)

    def test_free_threaded_variant_and_independent_republisher_have_visible_identities(self):
        page = self.documentation['catalog']['uv-purifier']
        points = page['compatibility']['testedPoints']
        threaded = [point for point in points if 'Target freeThreaded=true' in point['notes']]
        self.assertTrue(threaded)
        for point in threaded:
            runtime = next(c for c in point['components'] if c['role'] == 'project-runtime')
            self.assertEqual(runtime['name'], 'Python (free-threaded)')
        for point in points:
            if 'ordinary-republisher' in point['operations']:
                tools = {c['name']: c['version'] for c in point['components'] if c['role'] == 'native-tool'}
                self.assertIn('uv', tools)
                self.assertIn('uv (ordinary republisher)', tools)
        body = render_compatibility(page, self.contract)
        self.assertIn('Project runtime: Python (free-threaded)', body)
        self.assertIn('Build tool / package manager: uv (ordinary republisher)', body)

    def test_gradle_76_cold_point_keeps_execution_and_byte_parity_scoped(self):
        page = copy.deepcopy(self.documentation['catalog']['gradle-purifier'])
        point = next(p for p in page['compatibility']['testedPoints']
                     if p['id'] == 'gradle-7.6.6-java17-compiler8-runtime8-cold-x86_64-linux')
        components = {c['role']: c['version'] for c in point['components']}
        self.assertEqual(components, {'native-tool': '7.6.6', 'native-tool-runtime': '17.0.20.1+1',
                                     'compiler': '8u504-b01', 'project-runtime': '8u504-b01'})
        self.assertEqual(point['system'], 'x86_64-linux')
        self.assertIn('native-published-class-byte-equality', point['operations'])
        self.assertNotIn('pure-native-byte-equality', point['operations'])
        self.assertIn('ordinary-java-consumer', point['operations'])
        self.assertNotIn('ordinary-maven-consumer', point['operations'])
        self.assertNotIn('ordinary-gradle-consumer', point['operations'])
        page['compatibility']['testedPoints'] = [point]
        body = render_compatibility(page, self.contract)
        self.assertIn('Runtime running the tool: OpenJDK 17.0.20.1+1', body)
        self.assertIn('Project compiler: OpenJDK 8u504-b01', body)
        self.assertIn('Project runtime: OpenJDK 8u504-b01', body)
        self.assertIn('default :test task selects Java 17 but is skipped', ' '.join(point['notes']))
        self.assertIn('Whole native and published JAR bytes differ', ' '.join(point['notes']))
        self.assertIn('native-published-class-byte-equality', point['operations'])
        self.assertNotIn('Matching native/Nix publication bytes', body)
        self.assertFalse(page['compatibility']['supportedRanges'])

    def test_tested_roles_remain_distinct_and_do_not_create_a_range(self):
        page = copy.deepcopy(self.page)
        # This original fixture is x86-only even after other points gain ARM evidence.
        page['compatibility']['testedPoints'] = [point for point in page['compatibility']['testedPoints']
                                                 if point['id'] == 'npm6-node12-pure']
        body = render_compatibility(page, self.contract)
        self.assertIn('Build tool / package manager: npm 6.14.16', body)
        self.assertIn('Project runtime: Node.js 12.22.12', body)
        self.assertIn('Capture / build helper: Node.js 24.21.0', body)
        self.assertIn('x86_64-linux', body)
        self.assertNotIn('aarch64-linux', body.split('### Tested combinations', 1)[1])
        self.assertFalse(page['compatibility']['supportedRanges'])
        self.assertNotIn('### Supported ranges', body)

    def test_combinations_show_compact_choices_with_scoped_details(self):
        page = copy.deepcopy(self.documentation['catalog']['maven-purifier'])
        original = copy.deepcopy(page)
        body = render_compatibility(page, self.contract)
        table = body.split('### Tested combinations', 1)[1].split('### Requirements', 1)[0]
        summaries = re.findall(r'<summary><span class="tested-combination-labels">(.*?)</span></summary>', table)
        self.assertTrue(summaries)
        self.assertNotIn('Checked operations', ' '.join(summaries))
        self.assertNotIn('Exact Maven distribution selected by wrapper', ' '.join(summaries))
        self.assertIn('Native lock capture', table)
        self.assertIn('<summary>Limits and source evidence</summary>', table)
        self.assertNotIn('<details open', table)
        for point in page['compatibility']['testedPoints']:
            self.assertIn(point['system'], table)
            for component in point['components']:
                self.assertIn(component['version'], table)
        self.assertEqual(table.count('[Checks]('), len(page['compatibility']['testedPoints']))
        self.assertEqual(page, original)

    def test_grouping_preserves_helper_variation_and_platform_scope(self):
        page = copy.deepcopy(self.page)
        first = copy.deepcopy(page['compatibility']['testedPoints'][0])
        second = copy.deepcopy(first)
        second['id'] = 'same-toolchain-arm'
        second['system'] = 'aarch64-linux'
        third = copy.deepcopy(first)
        third['id'] = 'different-helper'
        next(c for c in third['components'] if c['role'] == 'host-helper')['version'] = '99.0.0'
        page['compatibility']['testedPoints'] = [first, second, third]
        body = render_compatibility(page, self.contract)
        self.assertEqual(body.count('<details class="tested-combination"'), 2)
        self.assertEqual(body.count('[Checks]('), 3)
        self.assertIn('Linux x86-64 · Linux ARM64', body)
        self.assertIn('Capture / build helper: Node.js 99.0.0', body)
        self.assertEqual(len(page['compatibility']['testedPoints']), 3)

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
