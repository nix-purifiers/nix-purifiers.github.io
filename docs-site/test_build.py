import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from build import build
from content import render


@unittest.skipUnless(shutil.which('nix'), 'Nix is needed for model integration tests')
class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        result = subprocess.run(['nix', 'eval', '--json', '.#documentation'],
                                cwd=cls.root, check=True, capture_output=True, text=True)
        cls.documentation = json.loads(result.stdout)

    def test_builds_real_pages_preserves_homepage_and_exports_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build(self.documentation, output)
            ant = (output / 'ant-purifier/index.md').read_text()
            docker = (output / 'docker-purifier/index.md').read_text()
            self.assertIn('ivy.lock.xml, ant-purifier.lock.json', ant)
            self.assertIn('docker build .', docker)
            self.assertIn('networkless software VM', docker)
            self.assertIn('## Development loop', ant)
            self.assertEqual((output / 'index.html').read_bytes(), (self.root / 'index.html').read_bytes())
            self.assertFalse((output / 'index.md').exists())
            self.assertIn('feature_matrix: "/ant-purifier/features.html"', ant)
            matrix = (output / 'ant-purifier/features.md').read_text()
            self.assertIn('ivy.lock.xml, ant-purifier.lock.json', matrix)
            self.assertIn('Unknown:', matrix)
            audit = json.loads((output / 'content-variations.json').read_text())
            self.assertEqual(audit['ant-purifier']['unresolved']['credentials']['state'], 'unknown')
            self.assertEqual(json.loads((output / 'catalog.json').read_text()), self.documentation)

    def test_rebuild_removes_the_previous_generated_tracking_landing_page(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'index.md').write_text('# Purifier reference\n\nCoverage and unresolved facts.\n')
            build(self.documentation, output)
            self.assertFalse((output / 'index.md').exists())
            self.assertEqual((output / 'index.html').read_bytes(), (self.root / 'index.html').read_bytes())

    def test_contradictory_copy_rejected_before_output(self):
        documentation = copy.deepcopy(self.documentation)
        documentation['catalog']['ant-purifier']['facts']['relock']['value'] = 're-resolves'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'site'
            with self.assertRaisesRegex(ValueError, 'relock'):
                build(documentation, output)
            self.assertFalse(output.exists())

    def test_shared_variant_tracks_different_behavior(self):
        page = copy.deepcopy(self.documentation['catalog']['ant-purifier'])
        page['facts']['relock']['value'] = 're-resolves'
        page['sections']['workflow']['use'] = 'fresh'
        page['sections']['workflow'].pop('details', None)
        markdown, _ = render(page, self.documentation['contract'])
        self.assertIn('does not retain existing pins', markdown)
        self.assertNotIn('Relocking retains existing pins.', markdown)

    def test_documented_commands_come_from_the_operational_recipe(self):
        page = copy.deepcopy(self.documentation['catalog']['ant-purifier'])
        page['operations']['lock']['arguments'] = ['new-lock-command']
        markdown, _ = render(page, self.documentation['contract'])
        self.assertIn('ant-purifier new-lock-command', markdown)

    def test_export_prepares_independent_project_without_touching_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            export = base / 'catalog.json'
            export.write_text(json.dumps(self.documentation))
            output = base / 'site'
            (output / 'maven').mkdir(parents=True)
            package = output / 'maven/plugin.jar'
            package.write_bytes(b'published-package')
            command = [sys.executable, str(self.root / 'docs-site/prepare.py'),
                       '--repository', 'nix-purifiers/ant-purifier', '--output', str(output)]
            subprocess.run(command + ['--catalog', str(export)], check=True, capture_output=True)
            self.assertIn('## Development loop', (output / 'index.md').read_text())
            self.assertEqual(package.read_bytes(), b'published-package')
            self.assertTrue((output / 'system.json').exists())
            self.assertTrue((output / 'features.md').exists())
            self.assertIn('feature_matrix: /features.html', (output / 'index.md').read_text())
            readme = base / 'README.md'
            readme.write_text('# Legacy\n\n[Example](examples/hello)\n')
            subprocess.run(command + ['--readme', str(readme)], check=True, capture_output=True)
            self.assertFalse((output / 'system.json').exists())
            self.assertFalse((output / 'content-variations.json').exists())
            self.assertFalse((output / 'features.md').exists())
            self.assertNotIn('feature_matrix:', (output / 'index.md').read_text())
            self.assertIn('https://github.com/nix-purifiers/ant-purifier/blob/main/examples/hello',
                          (output / 'index.md').read_text())
            self.assertEqual(package.read_bytes(), b'published-package')


if __name__ == '__main__':
    unittest.main()
