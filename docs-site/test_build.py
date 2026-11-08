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
            self.assertEqual((output / 'robots.txt').read_text(), 'User-agent: *\nAllow: /\n')
            config = json.loads((output / '_config.yml').read_text())
            self.assertEqual(config['feature_matrices']['nix-purifiers/ant-purifier'],
                             '/ant-purifier/features.html')
            matrix = (output / 'ant-purifier/features.md').read_text()
            self.assertIn('ivy.lock.xml, ant-purifier.lock.json', matrix)
            self.assertIn('Unknown:', matrix)
            self.assertNotIn('| Sources |', matrix)
            self.assertNotIn('README.md#', matrix)
            self.assertIn('LSP diagnostics</span> | Supported', matrix)
            self.assertIn('LSP definition lookup</span> | Supported', matrix)
            self.assertNotIn('jdtls', matrix)
            self.assertIn('reference.html#language-tooling-integration', ant)
            for name in self.documentation['catalog']:
                page = (output / name / 'index.md').read_text()
                self.assertNotIn('Keep your existing editor', page)
                self.assertNotIn('## Editor', page)
                if '## Language' in page:
                    self.assertIn('## Language tooling integration', page)
            helm_guide = (output / 'helm-purifier/reference.md').read_text()
            self.assertIn('## Language tooling integration', helm_guide)
            self.assertIn('<a id="editor"></a>', helm_guide)
            self.assertNotIn('## Editor', helm_guide)
            bun = (output / 'bun-purifier/index.md').read_text()
            self.assertIn('reference.html#language-tooling-integration', bun)
            self.assertIn('reference.html#project-projections', ant)
            self.assertIn('Incoming projections', matrix)
            self.assertIn('Outgoing projections', matrix)
            for name in self.documentation['catalog']:
                overview = (output / name / 'index.md').read_text()
                self.assertNotIn('## Version compatibility', overview)
                self.assertIn('reference.html#version-compatibility', overview)
                self.assertNotIn('## Language tooling integration', overview)
                self.assertNotIn('## Project projections', overview)
                original, _ = render(self.documentation['catalog'][name], self.documentation['contract'])
                from reference import source_sections
                original_sections = dict(source_sections(original)[1])
                actual_sections = dict(source_sections(overview)[1])
                for title in ('Quickstart', 'Development loop', 'Working offline', 'Supported scope'):
                    if title in original_sections:
                        self.assertEqual(actual_sections[title], original_sections[title])
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

    def test_native_and_resource_projection_scopes_render_with_shared_labels(self):
        for name in ('meson-purifier', 'cmake-purifier'):
            with self.subTest(name=name):
                page = self.documentation['catalog'][name]
                text, _ = render(page, self.documentation['contract'])
                self.assertIn('Incoming formats: Resource bundles.', text)
                self.assertIn('Outgoing formats: Native shared libraries, Resource bundles.', text)
                self.assertIn('resourceDependencies', text)
                self.assertIn('projections.python-ffi', text)
                self.assertIn('No generic typed incoming C/C++ library projection adapter', text)
                if name == 'cmake-purifier':
                    self.assertIn('legacy-external-v1 is acquisition-only', text)
        sbt, _ = render(self.documentation['catalog']['sbt-purifier'],
                        self.documentation['contract'])
        self.assertIn('Incoming formats: Maven, Ivy.', sbt)

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
            self.assertEqual(json.loads((output / '_config.yml').read_text())['feature_matrices'],
                             {'nix-purifiers/ant-purifier': '/features.html'})
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
