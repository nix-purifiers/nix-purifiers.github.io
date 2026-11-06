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
        self.q = copy.deepcopy(self.data['projects']['gradle-purifier'])

    def test_every_modeled_project_has_an_assessment(self):
        root = Path(__file__).resolve().parents[1]
        modeled = set(json.loads((root / 'model/repositories.json').read_text())) - {'purifier'}
        self.assertLessEqual(modeled, set(self.data['projects']))
        self.assertIn('inkscape-purifier', self.data['projects'])
        self.assertNotIn('gnome-purifier', self.data['projects'])

    def test_foreign_repository_does_not_inherit_same_name_tier(self):
        self.assertIsNone(for_repository('other-owner/go-purifier', self.data))
        self.assertEqual(for_repository('nix-purifiers/go-purifier', self.data)['tier'], 3)

    def test_ci_link_does_not_invent_a_success_result(self):
        self.assertEqual(evidence_label('https://github.com/owner/repo/actions/runs/1/job/2'), 'Native CI job')
        self.assertEqual(evidence_label('https://github.com/owner/repo/actions/runs/1'), 'Native CI run')

    def test_go_exact_points_do_not_establish_broad_compatibility(self):
        go = self.data['projects']['go-purifier']
        self.assertEqual(go['tier'], 3)
        self.assertEqual(go['criteria']['longCompatibility']['state'], 'unreviewed')
        self.assertIn('1.0.3', go['criteria']['longCompatibility']['summary'])
        self.assertIn('1.26.10', go['criteria']['longCompatibility']['summary'])
        self.assertEqual(go['criteria']['manySamples']['state'], 'unreviewed')
        self.assertEqual(go['criteria']['nonEolVersions']['state'], 'unreviewed')
        self.assertTrue(any(sample['name'].startswith('fzf ') for sample in go['sampleBuilds']))

    def test_platform_declaration_or_evaluation_cannot_promote(self):
        self.q['tier'] = 2
        with self.assertRaisesRegex(ValueError, 'evidenced criteria'):
            validate(self.q)

    def test_even_tier_four_requires_evaluation(self):
        self.q['tier'] = 4
        self.q['criteria']['evaluation']['state'] = 'unreviewed'
        with self.assertRaisesRegex(ValueError, 'evaluation evidence'):
            validate(self.q)

    def test_missing_sample_prevents_tier_three(self):
        self.q['sampleBuilds'] = []
        with self.assertRaisesRegex(ValueError, 'evidenced criteria'):
            validate(self.q)
        self.q['tier'] = 4
        validate(self.q)

    def test_met_criteria_require_sources(self):
        self.q['criteria']['linux']['evidence'] = []
        with self.assertRaisesRegex(ValueError, 'require evidence'):
            validate(self.q)

    def test_promotion_needs_each_reviewed_judgment(self):
        for item in self.q['criteria'].values():
            item.update(state='met', summary='Reviewed test evidence.', evidence=['https://example.test/proof'])
        self.q['tier'] = 1
        validate(self.q)
        self.q['criteria']['manySamples']['state'] = 'unreviewed'
        with self.assertRaisesRegex(ValueError, 'evidenced criteria'):
            validate(self.q)
        self.q['tier'] = 2
        validate(self.q)

    def test_duplicate_samples_do_not_inflate_breadth(self):
        self.q['sampleBuilds'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicate sample'):
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
        source = '<ul><li><a href="/gradle-purifier/">gradle-purifier</a>, for Gradle</li></ul>'
        result = homepage(source, self.data)
        self.assertIn('<h2 id="tier-3">Tier 3</h2>', result)
        self.assertIn('<a href="/gradle-purifier/">gradle-purifier</a>, for Gradle', result)
        self.assertNotIn('tier-badge', result)
        for empty in [1, 2, 4]:
            self.assertNotIn(f'<h2 id="tier-{empty}">', result)
        self.assertEqual(result, homepage(result, self.data))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            install_theme(target)
            self.assertEqual(json.loads((target / '_data/purifier_quality.json').read_text()), self.data['projects'])
            self.assertIn('quality.tier', (target / '_layouts/default.html').read_text())

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
        self.assertIn('| Unreviewed |', text)
        self.assertNotIn('[source 1]', text)
        self.assertNotIn('|\n\n|', text)


if __name__ == '__main__':
    unittest.main()
