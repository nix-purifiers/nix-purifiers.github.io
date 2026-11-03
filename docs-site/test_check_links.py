import json
from pathlib import Path
import tempfile
import unittest

from check_links import check
from content import source_links


class RenderedLinkTests(unittest.TestCase):
    def test_generated_destinations_stay_on_the_documentation_site(self):
        markdown = '[Native reference](reference.html#editor) and [Feature matrix](features.html)'
        self.assertEqual(source_links(markdown, 'nix-purifiers/bun-purifier'), markdown)
        self.assertIn('https://github.com/nix-purifiers/bun-purifier/blob/main/tests/check.py',
                      source_links('[test](tests/check.py)', 'nix-purifiers/bun-purifier'))

    def test_required_navigation_and_resolved_destinations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, site = root / 'source', root / 'site'
            source.mkdir()
            site.mkdir()
            (source / '_config.yml').write_text(json.dumps({
                'baseurl': '/bun-purifier',
                'feature_matrices': {'nix-purifiers/bun-purifier': '/features.html'},
            }))
            navigation = '<a href="/bun-purifier/features.html">Feature matrix</a>'
            for name in ('index.html', 'reference.html', 'features.html'):
                (site / name).write_text(navigation)
            self.assertEqual(check(source, site), {'pages': 3, 'matrixLinks': 3})
            for broken in (
                '',
                navigation + '<a href="reference-missing.html">Native reference</a>',
                navigation + '<a href="https://github.com/nix-purifiers/bun-purifier/blob/main/features.html">Matrix</a>',
                navigation + '<a href="/features.html">Matrix</a>',
            ):
                (site / 'index.html').write_text(broken)
                with self.subTest(broken=broken), self.assertRaises(ValueError):
                    check(source, site)


if __name__ == '__main__':
    unittest.main()
