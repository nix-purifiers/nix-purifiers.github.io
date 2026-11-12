import copy
import json
import re
from pathlib import Path
import unittest

from compatibility import validate, render_compatibility, render_exact_versions, packaged_components, packaged_match, tested_combinations, verified_platforms, EMPTY
from content import render, feature_matrix
from reference import reference_text
from export import validate_version_coverage


class CompatibilityTests(unittest.TestCase):
    def test_maven_choices_hide_internal_helpers_and_collapse_java_build_ids(self):
        page = self.documentation['catalog']['maven-purifier']
        original = copy.deepcopy(page)
        body = render_compatibility(page, self.contract)
        self.assertIn('| Maven | 3.10.0 (without a Maven wrapper) |', body)
        self.assertIn('2.2.1, 3.0.5', body)
        self.assertIn('| Java | 21; 8 (Maven 2 / 3.0 fallback) | 8, 17, 21 |', body)
        self.assertIn('| Linux | ARM64 | Yes | Tested |', body)
        self.assertIn('| macOS | ARM64 | Yes | Tested |', body)
        self.assertNotIn('Python', body)
        self.assertNotIn('21.0.12.1+1', body)
        self.assertNotIn('8u504-b01', body)
        self.assertNotIn('Packaged versions', body)
        self.assertNotIn('Version definitions', body)
        self.assertNotIn('### Tested combinations', body)
        self.assertIn('do not imply every combination or an entire version range', body)
        self.assertIn('Maven 2.2.1 can consume Nix inputs through the sandbox builder', body)
        matrix = feature_matrix(page, self.contract)
        self.assertIn('Python 3.14.8', matrix)
        self.assertIn('21.0.12.1+1', matrix)
        self.assertEqual(page, original)

    def test_recorded_versions_include_packaged_defaults_without_becoming_an_allowlist(self):
        page = copy.deepcopy(self.documentation['catalog']['maven-purifier'])
        component = next(c for c in page['compatibility']['defaults'] if c['role'] == 'native-tool')
        page['compatibility']['testedPoints'][0]['components'].append(dict(
            role=component['role'], name=component['name'], version=component['version']))
        body = render_compatibility(page, self.contract)
        row = next(line for line in body.splitlines() if line.startswith('| Maven |'))
        self.assertIn(component['version'], row.split('|')[3])
        self.assertIn('Packaged defaults', body)
        self.assertIn('not an allowlist', body)
        self.assertIn('preserve your existing core runtime without requiring a Nix SDK', body)
        self.assertIn('Fully sandboxed builds can require specific runtime versions', body)
        self.assertIn('those build requirements are separate from local adoption', body)
        self.assertIn('source revisions and platforms', body)
        self.assertNotIn('Other verified versions', body)
        self.assertIn('| Packaged toolchain | Recorded workflow |', body)
        self.assertNotIn('| Availability |', body)
        self.assertIn('an unrecorded result does not mean a platform is unavailable', body)

    def test_helper_changes_do_not_change_user_version_choices(self):
        for name in ['maven-purifier', 'npm-purifier', 'bundler-purifier']:
            page = copy.deepcopy(self.documentation['catalog'][name])
            before = render_compatibility(page, self.contract)
            for component in page['compatibility']['defaults']:
                if component['role'] == 'host-helper':
                    component['version'] = '99.99.99'
                    component['systems'] = ['invented-internal-platform']
            for point in page['compatibility']['testedPoints']:
                for component in point['components']:
                    if component['role'] in ('host-helper', 'publisher-helper'):
                        component['version'] = '99.99.99'
            self.assertEqual(render_compatibility(page, self.contract), before)

    def test_distinct_gradle_manager_compiler_and_runtime_choices_stay_distinct(self):
        page = self.documentation['catalog']['gradle-purifier']
        body = render_compatibility(page, self.contract)
        self.assertIn('Java (runs the tool)', body)
        self.assertIn('Java (compiles the project)', body)
        self.assertIn('Java (runs the project)', body)
        self.assertIn('| Gradle | Project-selected |', body)
        self.assertIn('| Java (compiles the project) | Project-selected |', body)
        self.assertIn('| Java (runs the project) | Project-selected |', body)
        self.assertNotIn('21.0.12.1+1', body)

    def test_different_packaged_java_roles_do_not_merge_without_test_points(self):
        page = copy.deepcopy(self.documentation['catalog']['maven-purifier'])
        data = page['compatibility']
        data['testedPoints'] = []
        runtime = next(c for c in data['defaults'] if c['role'] == 'native-tool-runtime')
        data['defaults'] = [dict(runtime, version='17.0.19'),
                            dict(runtime, role='compiler', version='8u504-b01')]
        body = render_compatibility(page, self.contract)
        self.assertIn('Java (runs the tool)', body)
        self.assertIn('Java (compiles the project)', body)

    def test_native_platform_review_requires_the_exact_architecture(self):
        page = copy.deepcopy(self.documentation['catalog']['maven-purifier'])
        review = page['quality']['derivationReview']['criteria']['linux']
        receipts = page['quality']['derivationReview']['derivations']
        review['derivations'] = [d for d in review['derivations'] if receipts[d]['system'] != 'aarch64-linux']
        body = render_compatibility(page, self.contract)
        self.assertIn('| Linux | ARM64 | Yes | Not recorded |', body)
        self.assertIn('| Linux | x86-64 | Yes | Tested |', body)
        review['derivations'].append('other-project:aarch64-linux:unrelated')
        self.assertEqual(render_compatibility(page, self.contract), body)

    def test_platform_receipt_fields_override_opaque_ids_and_reject_foreign_sources(self):
        page = copy.deepcopy(self.documentation['catalog']['maven-purifier'])
        data = page['compatibility']
        data['testedPoints'] = []
        review = page['quality']['derivationReview']
        criterion = review['criteria']['linux']
        identifier = next(i for i in criterion['derivations'] if review['derivations'][i]['system'] == 'aarch64-linux')
        receipt = review['derivations'][identifier]
        opaque = 'unrelated-name:x86_64-darwin:misleading'
        review['derivations'] = {opaque: receipt}
        criterion['derivations'] = [opaque]
        review['criteria']['darwin']['derivations'] = []
        self.assertEqual(verified_platforms(page, data), {'aarch64-linux'})
        receipt['build']['executedSystem'] = 'x86_64-linux'
        self.assertEqual(verified_platforms(page, data), set())
        receipt['build']['executedSystem'] = 'aarch64-linux'
        receipt['repository'] = 'another-owner/maven-purifier'
        self.assertEqual(verified_platforms(page, data), set())
        receipt['repository'] = page['repository']
        receipt['revision'] = '0' * 40
        self.assertEqual(verified_platforms(page, data), set())

    def test_gradle_review_platforms_are_independent_of_revision_style_ids(self):
        page = self.documentation['catalog']['gradle-purifier']
        self.assertIn('aarch64-darwin', verified_platforms(page, page['compatibility']))

    def with_test_evidence(self, page):
        return (render_exact_versions(page, self.contract)
                + "\n\n### Tested combinations\n\n"
                + tested_combinations(page["compatibility"]["testedPoints"],
                                      packaged_components(page["compatibility"]["defaults"])))

    def test_publisher_roles_keep_distinct_sdk_out_of_project_runtime_summary(self):
        page = copy.deepcopy(self.documentation['catalog']['bundler-purifier'])
        point = copy.deepcopy(page['compatibility']['testedPoints'][0])
        point['components'] = [
            {'role': 'native-tool', 'name': 'RubyGems', 'version': '1.0.1'},
            {'role': 'project-runtime', 'name': 'Ruby', 'version': '1.8.3'},
            {'role': 'publisher-tool', 'name': 'RubyGems', 'version': '1.3.5'},
            {'role': 'publisher-tool', 'name': 'Gemcutter artifact', 'version': '0.3.0'},
            {'role': 'publisher-tool', 'name': 'Gemcutter User-Agent report', 'version': '0.2.0'},
            {'role': 'publisher-runtime', 'name': 'Ruby', 'version': '1.8.4'},
            {'role': 'publisher-helper', 'name': 'json_pure', 'version': '1.8.6'},
        ]
        page['compatibility']['testedPoints'] = [point]
        validate(page['compatibility'])
        self.assertNotIn('tested-combination', render_compatibility(page, self.contract))
        body = feature_matrix(page, self.contract).split('## Tested combinations', 1)[1]
        summary = re.search(r'<summary>(.*?)</summary>', body).group(1)
        self.assertIn('Ruby 1.8.3', summary)
        self.assertIn('Separate publisher SDK', summary)
        self.assertNotIn('1.8.4', summary)
        self.assertNotIn('1.3.5', summary)
        self.assertIn('Publication tool: RubyGems 1.3.5', body)
        self.assertIn('Runtime running publication: Ruby 1.8.4', body)
        self.assertIn('Publication helper: json_pure 1.8.6', body)
        self.assertIn('Gemcutter artifact 0.3.0', body)
        self.assertIn('Gemcutter User-Agent report 0.2.0', body)
        control = copy.deepcopy(point)
        control['id'] += '-publisher-control'
        control['components'][2]['version'] = '9.9.9'
        page['compatibility']['testedPoints'].append(control)
        validate(page['compatibility'])
        self.assertEqual(feature_matrix(page, self.contract).count('<details class="tested-combination"'), 2)

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
                self.assertNotIn("tested-combination", guide)
                self.assertNotIn("Checked operations", guide)
                self.assertNotIn("tested-combination", overview)
                matrix = feature_matrix(page, self.contract)
                self.assertEqual(matrix.count("<ul class=\"tested-operations\">"), len(page["compatibility"]["testedPoints"]))
                self.assertNotIn("href=\"#packaged-version-", matrix)
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
        body = self.with_test_evidence(page)
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
        body = self.with_test_evidence(page)
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
        body = self.with_test_evidence(page)
        self.assertIn('Build tool / package manager: npm 6.14.16', body)
        self.assertIn('Project runtime: Node.js 12.22.12', body)
        packaged = packaged_components(page['compatibility']['defaults'])
        helper = packaged_match(('host-helper', 'Node.js', '24.21.0'), {'x86_64-linux'}, packaged)
        self.assertIsNotNone(helper)
        self.assertIn('Capture / build helper: <a href="#' + helper['id'] + '">Node.js (packaged version)</a>', body)
        self.assertIn('id="' + helper['id'] + '"><span class="version-labels"><strong>Node.js 24.21.0</strong>', body)
        self.assertIn('x86_64-linux', body)
        self.assertNotIn('aarch64-linux', body.split('### Tested combinations', 1)[1])
        self.assertFalse(page['compatibility']['supportedRanges'])
        self.assertNotIn('### Supported ranges', body)

    def test_combinations_show_compact_choices_with_scoped_details(self):
        page = copy.deepcopy(self.documentation['catalog']['maven-purifier'])
        original = copy.deepcopy(page)
        body = self.with_test_evidence(page)
        table = body.split('### Tested combinations', 1)[1].split('### Requirements', 1)[0]
        summaries = re.findall(r'<summary><span class="tested-combination-labels(?: [^"]+)?">(.*?)</span></summary>', table)
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

    def packaged_go_case(self):
        page = copy.deepcopy(self.documentation['catalog']['go-purifier'])
        data = page['compatibility']
        data['defaults'] = [item for item in data['defaults'] if item['name'] == 'Go']
        version = data['defaults'][0]['version']
        data['testedPoints'] = [next(point for point in data['testedPoints']
                                   if any(c['role'] == 'native-tool' and c['version'] == version
                                          for c in point['components']))]
        return page

    def test_packaged_cards_combine_exact_shared_values_without_losing_roles(self):
        page = self.packaged_go_case()
        original = copy.deepcopy(page)
        body = self.with_test_evidence(page)
        packaged, tested = body.split('### Tested combinations', 1)
        version = page['compatibility']['defaults'][0]['version']
        self.assertEqual(packaged.count('<li class="packaged-version"'), 1)
        self.assertEqual(packaged.count('Go ' + version), 1)
        self.assertIn('Build tool / package manager; Project compiler', packaged)
        self.assertNotIn('| Selection | Component | Version | Platforms |', packaged)
        summary = re.search(r'<summary><span class="tested-combination-labels[^\"]*">(.*?)</summary>', tested).group(1)
        self.assertIn('Go (packaged version)', summary)
        self.assertIn('Also project compiler', summary)
        self.assertNotIn(version, summary)
        self.assertIn('[Checks](', tested)
        self.assertEqual(page, original)

    def test_packaged_references_require_exact_role_name_version_and_platform(self):
        for field in ['role', 'name', 'version', 'systems']:
            page = self.packaged_go_case()
            for item in page['compatibility']['defaults']:
                item[field] = {'role': 'host-helper', 'name': 'Another Go',
                               'version': '999.0.0', 'systems': ['aarch64-darwin']}[field]
            body = self.with_test_evidence(page).split('### Tested combinations', 1)[1]
            with self.subTest(field=field):
                self.assertNotIn('href="#packaged-version-', body)
                for component in page['compatibility']['testedPoints'][0]['components']:
                    self.assertIn(component['name'] + ' ' + component['version'], body)

    def test_shared_test_summary_does_not_extend_a_platform_limited_default(self):
        page = self.packaged_go_case()
        for item in page['compatibility']['defaults']:
            item['systems'] = ['x86_64-linux']
        point = copy.deepcopy(page['compatibility']['testedPoints'][0])
        point['id'] += '-arm-control'
        point['system'] = 'aarch64-linux'
        page['compatibility']['testedPoints'].append(point)
        body = self.with_test_evidence(page).split('### Tested combinations', 1)[1]
        self.assertNotIn('href="#packaged-version-', body)
        self.assertEqual(body.count('[Checks]('), 2)

    def test_packaged_choices_keep_platform_and_conditional_selection_differences(self):
        page = self.packaged_go_case()
        defaults = page['compatibility']['defaults']
        defaults[0]['systems'] = ['x86_64-linux']
        self.assertEqual(len(packaged_components(defaults)), 2)
        defaults[0]['systems'] = defaults[1]['systems'][:]
        alternatives = [dict(item, selection=selection) for selection in ['Profile A', 'Profile B']
                        for item in defaults]
        choices = packaged_components(alternatives)
        self.assertEqual(len(choices), 2)
        component = page['compatibility']['testedPoints'][0]['components'][0]
        self.assertIsNone(packaged_match((component['role'], component['name'], component['version']),
                                        {'x86_64-linux'}, choices))

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
        body = self.with_test_evidence(page)
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
