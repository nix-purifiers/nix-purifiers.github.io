import json
from pathlib import Path
import re
import unittest

from reference import guide_plan, reference_text, source_sections


class FullGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parent
        cls.documentation = json.loads((cls.root / 'catalog.json').read_text())

    def test_every_guide_follows_shared_order_and_has_a_distinct_opening(self):
        contract = json.loads((self.root / 'guide-contract.json').read_text())
        titles = {s['id']: s['title'] for s in self.documentation['contract']['sections']}
        order = [titles[s['titleFrom']] if 'titleFrom' in s else s['title']
                 for s in contract['sections']]
        order.insert(1, self.documentation['contract']['versionCompatibility']['title'])
        for name, page in self.documentation['catalog'].items():
            with self.subTest(name=name):
                source = (self.root / 'references' / (name + '.md')).read_text()
                guide = reference_text(page['repository'], source, page)
                self.assertTrue(guide.startswith('# ' + name + ' full guide\n'))
                self.assertLess(guide.index('## Contents'), guide.index('## Setup and activation'))
                headings = [title for title, _ in source_sections(guide)[1] if title != 'Contents']
                self.assertEqual(headings, [title for title in order if title in headings])
                self.assertNotIn('Quickstart', headings)
                self.assertNotIn('## Editor\n', guide)
                self.assertNotIn('The reviewed guide has no separate', guide)

    def test_new_or_duplicated_source_sections_require_an_explicit_plan(self):
        text = (self.root / 'references/bun-purifier.md').read_text()
        for addition in ('\n## New native feature\n\nNeeds a section.\n',
                         '\n## Quickstart\n\nDuplicate source section.\n'):
            with self.subTest(addition=addition), self.assertRaisesRegex(ValueError, 'exactly once'):
                guide_plan('nix-purifiers/bun-purifier', text + addition)

    def test_markdown_examples_are_not_treated_as_document_structure(self):
        text = '# Project\n\nIntroduction.\n\n## Setup\n\n```markdown\n## Example heading\n```\n'
        _, sections = source_sections(text)
        self.assertEqual([title for title, _ in sections], ['Setup'])
        self.assertIn('## Example heading', sections[0][1])

    def test_duplicate_quickstart_moves_to_overview_but_native_detail_is_retained(self):
        page = self.documentation['catalog']['bun-purifier']
        source = (self.root / 'references/bun-purifier.md').read_text()
        guide = reference_text(page['repository'], source, page)
        setup = guide.split('## Setup and activation\n', 1)[1].split('\n## ', 1)[0]
        self.assertNotIn(page['values']['quickstart'], setup)
        self.assertIn('## Native integration', guide)
        self.assertIn('Nix reads\n`bun.lock`', guide)
        self.assertIn('<a id="building-the-project-with-nix"></a>', guide)


if __name__ == '__main__':
    unittest.main()
