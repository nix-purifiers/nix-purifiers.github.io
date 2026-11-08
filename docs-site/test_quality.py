import copy
import json
from pathlib import Path
import tempfile
import unittest

from quality import evidence_label, for_repository, homepage, registry, render_tiers, validate
from theme import install_theme


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.data = registry()
        self.q = copy.deepcopy(self.data['projects']['composer-purifier'])

    def test_v3_requires_human_use_without_changing_technical_evidence(self):
        self.assertEqual(self.data['version'], 3)
        docker = copy.deepcopy(self.data['projects']['docker-purifier'])
        self.assertEqual(docker['tier'], 4)
        self.assertEqual(docker['criteria']['firsthandUse']['state'], 'not-met')
        for key in ('evaluation', 'goodTests', 'linux', 'darwin', 'oneVersion', 'nonEolVersions'):
            self.assertEqual(docker['criteria'][key]['state'], 'met')
        docker['tier'] = 2
        with self.assertRaisesRegex(ValueError, 'evidenced criteria'):
            validate(docker)

    def test_production_registry_cannot_downgrade_or_omit_human_review(self):
        from unittest.mock import patch
        downgraded = copy.deepcopy(self.data); downgraded['version'] = 2
        with patch('quality.json.loads', return_value=downgraded), self.assertRaisesRegex(ValueError, 'version 3'):
            registry()
        legacy = copy.deepcopy(self.q)
        legacy.pop('humanUseReview')
        for key in ('firsthandUse', 'ongoingUse'): legacy['criteria'].pop(key)
        with self.assertRaisesRegex(ValueError, 'missing or unknown fields'): validate(legacy)

    def test_ci_cannot_be_relabelled_as_a_human_report(self):
        docker = copy.deepcopy(self.data['projects']['docker-purifier'])
        docker['criteria']['firsthandUse'].update(state='met', evidence=['https://github.com/example/tool/actions/runs/1'])
        docker['humanUseReview']['criteria']['firsthandUse'].update(state='met', gap=None)
        with self.assertRaisesRegex(ValueError, 'reviewed reports'):
            validate(docker)

    def test_audit_does_not_infer_ongoing_use_from_local_reports(self):
        self.assertEqual(sum(q['criteria']['firsthandUse']['state'] == 'met' for q in self.data['projects'].values()), 36)
        self.assertTrue(all(q['criteria']['ongoingUse']['state'] == 'not-met' for q in self.data['projects'].values()))
        self.assertNotIn(1, [q['tier'] for q in self.data['projects'].values()])

    def test_every_modeled_project_has_an_assessment(self):
        root = Path(__file__).resolve().parents[1]
        modeled = set(json.loads((root / 'model/repositories.json').read_text())) - {'purifier'}
        self.assertLessEqual(modeled, set(self.data['projects']))
        self.assertIn('inkscape-purifier', self.data['projects'])
        self.assertNotIn('gnome-purifier', self.data['projects'])

    def test_foreign_repository_does_not_inherit_same_name_tier(self):
        self.assertIsNone(for_repository('other-owner/go-purifier', self.data))
        self.assertEqual(for_repository('nix-purifiers/go-purifier', self.data)['tier'], 2)

    def test_ci_link_does_not_invent_a_success_result(self):
        self.assertEqual(evidence_label('https://github.com/owner/repo/actions/runs/1/job/2'), 'Native CI job')
        self.assertEqual(evidence_label('https://github.com/owner/repo/actions/runs/1'), 'Native CI run')

    def test_go_exact_points_do_not_establish_broad_compatibility(self):
        go = self.data['projects']['go-purifier']
        self.assertEqual(go['tier'], 2)
        self.assertEqual(go['criteria']['longCompatibility']['state'], 'not-met')
        self.assertIn('1.0.3', go['criteria']['longCompatibility']['summary'])
        self.assertIn('1.26.10', go['criteria']['longCompatibility']['summary'])
        self.assertEqual(go['criteria']['manySamples']['state'], 'met')
        self.assertEqual(go['criteria']['nonEolVersions']['state'], 'met')
        self.assertTrue(any(sample['name'].startswith('fzf') for sample in go['sampleBuilds']))

    def test_platform_declaration_or_evaluation_cannot_promote(self):
        self.q['tier'] = 2
        with self.assertRaisesRegex(ValueError, 'evidenced criteria'):
            validate(self.q)

    def test_even_tier_four_requires_evaluation(self):
        self.q['tier'] = 4
        self.q['criteria']['evaluation']['state'] = 'not-met'
        self.q['derivationReview']['criteria']['evaluation'].update(state='not-met', gap='No execution or evaluation receipt established.')
        with self.assertRaisesRegex(ValueError, 'evaluation evidence'):
            validate(self.q)

    def test_missing_sample_prevents_tier_three(self):
        self.q['sampleBuilds'] = []
        self.q['derivationReview']['sampleBuilds'] = []
        with self.assertRaises(ValueError):
            validate(self.q)

    def test_met_criteria_require_executable_derivations(self):
        self.q['derivationReview']['criteria']['linux']['derivations'] = []
        with self.assertRaisesRegex(ValueError, 'executable evidence'):
            validate(self.q)

    def test_explanatory_urls_are_not_the_capability_proof(self):
        self.q['criteria']['linux']['evidence'] = []
        validate(self.q)

    def test_unreviewed_and_changed_judgments_rejected(self):
        self.q['criteria']['manySamples']['state'] = 'unreviewed'
        with self.assertRaisesRegex(ValueError, 'invalid tier criterion'):
            validate(self.q)
        self.q['criteria']['manySamples']['state'] = 'not-met'
        self.q['criteria']['manySamples']['summary'] = 'Changed without reviewer evidence.'
        with self.assertRaisesRegex(ValueError, 'differs from assessment judgment'):
            validate(self.q)

    def test_every_review_is_complete_and_revision_bound(self):
        self.assertEqual(len(self.data['projects']), 96)
        for name, q in self.data['projects'].items():
            self.assertEqual(len(q['criteria']), 10)
            self.assertEqual(len(q['derivationReview']['criteria']), 8)
            self.assertNotIn('unreviewed', [c['state'] for c in q['criteria'].values()])
            changed = copy.deepcopy(q)
            changed['reviewedRevision'] = '0' * 40
            with self.assertRaises(ValueError):
                validate(changed, 'nix-purifiers/' + name)

    def test_sources_cannot_replace_an_execution_receipt(self):
        for e in self.q['derivationReview']['derivations'].values():
            if e.get('kind') != 'native-ci-execution':
                e['build'] = None
                e['outputNarHashes'] = {}
        with self.assertRaises(ValueError):
            validate(self.q)

    def test_duplicate_samples_do_not_inflate_breadth(self):
        self.q['sampleBuilds'] *= 2
        with self.assertRaisesRegex(ValueError, 'samples|duplicate sample'):
            validate(self.q)

    def test_unknown_fields_and_boolean_tier_rejected(self):
        self.q['tier'] = True
        with self.assertRaises(ValueError):
            validate(self.q)
        self.q['tier'] = 3
        self.q['criteria']['darwin']['declaredSystem'] = True
        with self.assertRaises(ValueError):
            validate(self.q)

    def test_homepage_and_shared_theme_use_same_registry(self):
        source = '<ul><li><a href="/tectonic-purifier/">tectonic-purifier</a>, for Tectonic</li></ul>'
        result = homepage(source, self.data)
        self.assertIn('<h2 id="tier-4">Tier 4</h2>', result)
        self.assertIn('<a href="/tectonic-purifier/">tectonic-purifier</a>, for Tectonic', result)
        self.assertNotIn('tier-badge', result)
        for empty in [1, 2, 3]:
            self.assertNotIn(f'<h2 id="tier-{empty}">', result)
        self.assertEqual(result, homepage(result, self.data))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            install_theme(target)
            self.assertEqual(json.loads((target / '_data/purifier_quality.json').read_text()), self.data['projects'])
            layout = (target / '_layouts/default.html').read_text()
            self.assertNotIn('quality.tier', layout)
            self.assertNotIn('site.data.purifier_quality', layout)
            self.assertIn('>Tier assessment</a>', layout)

    def test_homepage_groups_only_present_tiers_and_reclassifies_without_stale_headings(self):
        data = {'projects': {'go-purifier': {'tier': 1}, 'gradle-purifier': {'tier': 3}}}
        source = '<p>Intro</p><ul><li><a href="/go-purifier/">go-purifier</a>, for Go</li><li><a href="/gradle-purifier/">gradle-purifier</a>, for Gradle</li></ul><p>Footer</p>'
        result = homepage(source, data)
        self.assertLess(result.index('Tier 1</h2>'), result.index('Tier 3</h2>'))
        self.assertNotIn('Tier 2</h2>', result)
        self.assertNotIn('Tier 4</h2>', result)
        self.assertEqual(result.count('<li>'), 2)
        self.assertIn('<p>Intro</p>', result)
        self.assertIn('<p>Footer</p>', result)
        data['projects']['go-purifier']['tier'] = 3
        updated = homepage(result, data)
        self.assertNotIn('Tier 1</h2>', updated)
        self.assertEqual(updated.count('Tier 3</h2>'), 1)
        self.assertEqual(updated.count('<li>'), 2)

    def test_tier_page_has_all_definitions_and_published_projects(self):
        text = render_tiers(self.data)
        for tier in range(1, 5):
            self.assertIn(f'| {tier} |', text)
            populated = any(q['tier'] == tier for q in self.data['projects'].values())
            self.assertEqual(f'## Tier {tier}' in text, populated)
        for name in self.data['projects']:
            self.assertIn(f'### {name}', text)
        self.assertIn('not numerical cutoffs', text)
        self.assertIn('| Met |', text)
        self.assertNotIn('| Unreviewed |', text)
        self.assertIn('Not met means the inspected evidence', text)
        self.assertIn('/nix/store/', text)
        self.assertNotIn('[source 1]', text)
        self.assertNotIn('|\n\n|', text)


if __name__ == '__main__':
    unittest.main()
