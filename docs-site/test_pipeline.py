"""Documentation builds tolerate native drift, not invalid documentation."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root / 'site'
        original = Path(__file__).resolve().parent.parent
        shutil.copytree(original / 'docs-site', self.site / 'docs-site')
        shutil.copytree(original / 'model', self.site / 'model')
        for name in ('index.html', 'robots.txt'):
            shutil.copyfile(original / name, self.site / name)
        self.checkout = self.root / 'checkout'
        self.checkout.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.checkout)], check=True)
        (self.checkout / 'README.md').write_text('UNREVIEWED CURRENT CONTENT\n')
        (self.checkout / 'native.py').write_text('new native implementation\n')
        subprocess.run(['git', '-C', str(self.checkout), 'add', '.'], check=True)

    def run_prepare(self, repository='nix-purifiers/pnpm-purifier', strict=False):
        return subprocess.run([
            sys.executable, str(self.site / 'docs-site/prepare.py'),
            '--repository', repository, '--model',
            '--check-source' if strict else '--source-status', str(self.checkout),
            '--output', str(self.root / 'output'),
        ], cwd=self.checkout, capture_output=True, text=True)

    def test_changed_native_source_builds_coherent_reviewed_bundle(self):
        result = self.run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.root / 'output'
        status = json.loads((output / 'source-review.json').read_text())
        self.assertEqual(status['status'], 'update-needed')
        self.assertIn('native.py', status['changedFiles'])
        self.assertIn('UNREVIEWED', (self.checkout / 'README.md').read_text())
        self.assertNotIn('UNREVIEWED', (output / 'reference.md').read_text())
        page = json.loads((output / 'system.json').read_text())
        self.assertEqual(page['reviewedRevision'], status['documentedRevision'])
        self.assertNotIn('/blob/main/', (output / 'reference.md').read_text())
        self.assertNotIn('/tree/main/', (output / 'reference.md').read_text())

    def test_strict_maintainer_audit_still_rejects_drift(self):
        result = self.run_prepare(strict=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('needs source review', result.stderr)

    def test_library_uses_bundled_readme_and_scope(self):
        result = self.run_prepare('nix-purifiers/purifier')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.root / 'output'
        self.assertNotIn('UNREVIEWED', (output / 'index.md').read_text())
        scope = json.loads((output / 'library.json').read_text())
        status = json.loads((output / 'source-review.json').read_text())
        self.assertEqual(scope['reviewedRevision'], status['documentedRevision'])
        self.assertFalse((output / 'features.md').exists())

    def test_corrupt_model_is_a_hard_failure(self):
        catalog = self.site / 'docs-site/catalog.json'
        data = json.loads(catalog.read_text())
        data['catalog']['pnpm-purifier']['reviewedRevision'] = '0' * 40
        catalog.write_text(json.dumps(data))
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('revision', result.stderr)

    def test_missing_guide_is_a_hard_failure(self):
        (self.site / 'docs-site/references/pnpm-purifier.md').unlink()
        self.assertNotEqual(self.run_prepare().returncode, 0)

    def test_corrupt_library_reference_is_a_hard_failure(self):
        (self.site / 'docs-site/references/purifier.md').write_text('wrong guide')
        self.assertNotEqual(self.run_prepare('nix-purifiers/purifier').returncode, 0)

    def test_legacy_tool_review_cannot_restore_empty_version_pages_or_hide_corruption(self):
        name = 'pnpm-purifier'
        repository = 'nix-purifiers/' + name
        revision = 'd' * 40
        variant = self.site / 'docs-site/reviews' / name / revision
        variant.mkdir(parents=True)
        snapshot = {'repository': repository, 'revision': revision,
                    'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in self.checkout.iterdir() if p.is_file()}}
        (variant / 'source.json').write_text(json.dumps(snapshot))
        shutil.copyfile(self.site / 'docs-site/references' / (name + '.md'), variant / 'reference.md')
        page = json.loads((self.site / 'docs-site/catalog.json').read_text())['catalog'][name]
        page['reviewedRevision'] = revision
        page.pop('compatibility')
        (variant / 'page.json').write_text(json.dumps(page))
        result = self.run_prepare(repository)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / 'output/index.md').read_text()
        self.assertIn('reference.html#version-compatibility', text)
        guide = (self.root / 'output/reference.md').read_text()
        self.assertIn('### Default and selectable versions', guide)
        self.assertNotIn('have not yet been recorded for this purifier', guide)
        page['facts']['tool']['value'] = True
        (variant / 'page.json').write_text(json.dumps(page))
        self.assertNotEqual(self.run_prepare(repository).returncode, 0)

    def test_matching_variant_is_selected_and_invalid_pairing_is_not_drift(self):
        repository = 'nix-purifiers/purifier'
        revision = 'b' * 40
        variant = self.site / 'docs-site/reviews/purifier' / revision
        variant.mkdir()
        snapshot = {'repository': repository, 'revision': revision,
                    'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in self.checkout.iterdir() if p.is_file()}}
        (variant / 'source.json').write_text(json.dumps(snapshot))
        shutil.copyfile(self.checkout / 'README.md', variant / 'reference.md')
        library = json.loads((self.site / 'model/library.json').read_text())
        library['reviewedRevision'] = revision
        (variant / 'library.json').write_text(json.dumps(library))
        result = self.run_prepare(repository)
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads((self.root / 'output/source-review.json').read_text())
        self.assertEqual(status['status'], 'matched')
        self.assertEqual(status['documentedRevision'], revision)
        library['reviewedRevision'] = 'c' * 40
        (variant / 'library.json').write_text(json.dumps(library))
        result = self.run_prepare(repository)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must match', result.stderr)


if __name__ == '__main__':
    unittest.main()
