import copy
import json
from pathlib import Path
import unittest

from content import render_overview
from reference import reference_text


class ScopeContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parent
        documentation = json.loads((cls.root / 'catalog.json').read_text())
        cls.contract = documentation['contract']
        cls.contract.update(json.loads((cls.root / 'contract.json').read_text()))
        cls.catalog = documentation['catalog']

    def test_overview_names_the_wrapper_and_its_unlocked_behavior(self):
        overview = render_overview(self.catalog['go-purifier'], self.contract)[0]
        self.assertIn('## Using locked dependencies', overview)
        self.assertIn('<a id="native-integration"></a>', overview)
        self.assertIn('the supplied wrapper warns', overview)
        self.assertIn('usual dependency resolution', overview)
        self.assertNotIn('## Native integration', overview)

    def test_missing_lock_behavior_is_not_invented_for_preparation_or_unknown_facts(self):
        for page in [self.catalog['helm-purifier'], copy.deepcopy(self.catalog['go-purifier'])]:
            page = copy.deepcopy(page)
            page['facts']['missing_lock'] = {'state': 'unknown', 'reason': 'Not established.'}
            overview = render_overview(page, self.contract)[0]
            self.assertNotIn('the supplied wrapper warns', overview)

    def test_scope_overview_separates_categories_and_each_fact(self):
        page = self.catalog['go-purifier']
        overview = render_overview(page, self.contract)[0]
        scope = overview.split('## Supported scope', 1)[1].split('\n## ', 1)[0]
        self.assertIn('<div class="supported-scope" markdown="1">', scope)
        for title in ['Target systems', 'Dependency sources', 'Platform limits']:
            self.assertIn('### ' + title, scope)
        for name in ['platforms', 'dependency_sources', 'platform_notes']:
            for value in page['facts'][name]['value']:
                self.assertIn('- ' + value, scope)

    def test_guides_keep_source_lists_and_format_platform_facts_as_lists(self):
        for name in ['bun-purifier', 'go-purifier', 'maven-purifier']:
            page = self.catalog[name]
            guide = reference_text(page['repository'], (self.root / 'references' / (name + '.md')).read_text(), page)
            scope = guide.split('## Supported scope', 1)[1].split('\n## ', 1)[0]
            self.assertIn('<div class="supported-scope" markdown="1">', scope)
            for value in page['facts']['platforms']['value']:
                self.assertIn('- ' + value, scope)
            self.assertIn('- **', scope)
            self.assertIn('## Using locked dependencies', guide)
            self.assertEqual(guide.count('<a id="native-integration"></a>'), 1)
            self.assertNotIn('## Native integration', guide)


if __name__ == '__main__':
    unittest.main()
