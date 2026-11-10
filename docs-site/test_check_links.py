import json
from pathlib import Path
import tempfile
import unittest

from check_links import check
from content import source_links


class RenderedLinkTests(unittest.TestCase):
    def test_legacy_entry_requires_automatic_routing_and_fragment_preservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, site = root / 'source', root / 'site'
            source.mkdir()
            site.mkdir()
            (source / '_config.yml').write_text(json.dumps({'baseurl': '/old-site'}))
            target = 'https://nix-purifiers.github.io/projects/bun-purifier/reference.html'
            (source / 'reference.md').write_text('---\ncanonical_url: ' + json.dumps(target) + '\n---\n')
            valid = ('<link rel="canonical" href="' + target + '">'
                     '<meta http-equiv="refresh" content="0;url=' + target + '">'
                     '<script>location.replace(' + json.dumps(target) + '+location.search+location.hash);</script>')
            for broken in [valid.replace('+location.hash', ''),
                           valid.replace('<meta http-equiv="refresh"', '<meta data-disabled="refresh"'),
                           '<a href="' + target + '">Continue</a>']:
                (site / 'reference.html').write_text(broken)
                with self.subTest(broken=broken), self.assertRaisesRegex(ValueError, 'automatically route'):
                    check(source, site)
            (site / 'reference.html').write_text(valid)
            self.assertEqual(check(source, site), {'pages': 1, 'matrixLinks': 0})

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
            navigation = ('<a href="/bun-purifier/features.html">Feature matrix</a>'
                          '<a href="/bun-purifier/reference.html">Full guide</a>')
            for name in ('index.html', 'reference.html', 'features.html'):
                (site / name).write_text(navigation)
            self.assertEqual(check(source, site), {'pages': 3, 'matrixLinks': 3})
            for broken in (
                '',
                navigation + '<a href="reference-missing.html">Native reference</a>',
                navigation + '<a href="https://github.com/nix-purifiers/bun-purifier/blob/main/features.html">Matrix</a>',
                navigation + '<a href="/features.html">Matrix</a>',
                navigation + '<a href="reference.html">Native reference</a>',
                navigation.replace('Full guide', 'Native reference'),
            ):
                (site / 'index.html').write_text(broken)
                with self.subTest(broken=broken), self.assertRaises(ValueError):
                    check(source, site)

    def test_canonical_namespace_survives_poisoned_project_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, site = root / 'source', root / 'site'
            source.mkdir()
            project = site / 'projects/bun-purifier'
            project.mkdir(parents=True)
            canonical = 'https://nix-purifiers.github.io/projects/bun-purifier/'
            (source / '_config.yml').write_text(json.dumps({
                'baseurl': '',
                'feature_matrices': {'nix-purifiers/bun-purifier': '/projects/bun-purifier/features.html'},
                'documentation_roots': {'nix-purifiers/bun-purifier': '/projects/bun-purifier/'},
            }))
            navigation = ('<a href="/projects/bun-purifier/features.html">Feature matrix</a>'
                          '<a href="/projects/bun-purifier/reference.html">Full guide</a>')
            for name in ('index.html', 'reference.html', 'features.html'):
                (project / name).write_text(navigation)
            legacy = site / 'bun-purifier'
            legacy.mkdir()
            (legacy / 'index.html').write_text('<h1>POISONED stale claims</h1>')
            (site / 'index.html').write_text(f'<a href="{canonical}">Documentation</a>')
            self.assertEqual(check(source, site), {'pages': 5, 'matrixLinks': 3})
            (site / 'index.html').write_text(f'<a href="{canonical}missing.html">Missing</a>')
            with self.assertRaisesRegex(ValueError, 'missing canonical documentation destination'):
                check(source, site)


if __name__ == '__main__':
    unittest.main()
