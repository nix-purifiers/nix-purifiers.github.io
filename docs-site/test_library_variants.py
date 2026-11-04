"""Exact-source library reviews remain separate from native-tool pages."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class LibraryVariantTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.site = self.root / 'site'
        original = Path(__file__).resolve().parent
        shutil.copytree(original, self.site / 'docs-site', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(original.parent / 'model', self.site / 'model')
        for filename in ('index.html', 'robots.txt'):
            shutil.copyfile(original.parent / filename, self.site / filename)
        self.checkout = self.root / 'checkout'
        self.checkout.mkdir()
        subprocess.run(['git', 'init', str(self.checkout)], check=True, capture_output=True)
        self.repository = 'nix-purifiers/purifier'
        self.main_revision, self.revision = 'a' * 40, 'b' * 40
        self.readme = self.checkout / 'README.md'
        self.readme.write_text('# Library\n\nCanonical guide.\n')
        subprocess.run(['git', '-C', str(self.checkout), 'add', '.'], check=True)
        self.manifest = self.site / 'model/repositories.json'
        self.write(self.manifest, {'purifier': self.snapshot(self.main_revision)})
        self.canonical = json.loads((self.site / 'model/library.json').read_text())
        self.canonical['reviewedRevision'] = self.main_revision
        self.write(self.site / 'model/library.json', self.canonical)
        self.canonical_before = (self.site / 'model/library.json').read_bytes()
        self.readme.write_text('# Library\n\nBranch guide: [API](nix/lib/api.nix).\n')
        self.variant = self.site / 'docs-site/reviews/purifier' / self.revision
        self.variant.mkdir(parents=True)
        self.write(self.variant / 'source.json', self.snapshot(self.revision))
        self.library = dict(self.canonical, reviewedRevision=self.revision,
                            validation=['Explicit branch validation.'])
        self.write(self.variant / 'library.json', self.library)
        (self.variant / 'reference.md').write_bytes(self.readme.read_bytes())

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value))

    def snapshot(self, revision):
        return {'repository': self.repository, 'revision': revision,
                'files': {'README.md': hashlib.sha256(self.readme.read_bytes()).hexdigest()}}

    def prepare(self, model=True):
        output = self.root / 'output'
        args = [sys.executable, str(self.site / 'docs-site/prepare.py'),
                '--repository', self.repository, '--check-source', str(self.checkout),
                '--readme', str(self.readme), '--output', str(output)]
        if model:
            args.append('--model')
        result = subprocess.run(args, capture_output=True, text=True)
        return result, output

    def assert_rejected(self, message):
        result, output = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertFalse(output.exists())

    def test_matching_library_uses_paired_scope_and_guide(self):
        result, output = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((output / 'library.json').read_text()), self.library)
        text = (output / 'index.md').read_text()
        self.assertIn('Explicit branch validation.', text)
        self.assertIn('Branch guide:', text)
        self.assertIn('/blob/' + self.revision + '/nix/lib/api.nix', text)
        self.assertFalse((output / 'system.json').exists())
        self.assertEqual((self.site / 'model/library.json').read_bytes(), self.canonical_before)

    def test_canonical_library_behavior_is_preserved(self):
        self.readme.write_text('# Library\n\nCanonical guide.\n')
        result, output = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (output / 'index.md').read_text()
        self.assertIn('Canonical guide.', text)
        self.assertIn('Target systems:', text)
        self.assertNotIn('Explicit branch validation.', text)
        self.assertFalse((output / 'library.json').exists())

    def test_unreviewed_source_is_rejected(self):
        self.readme.write_text('Unreviewed\n')
        self.assert_rejected('needs source review')

    def test_ambiguous_reviews_are_rejected(self):
        shutil.copytree(self.variant, self.variant.parent / 'duplicate')
        self.assert_rejected('multiple reviewed variants')

    def test_model_must_match_source_repository_and_revision(self):
        for key, value in [('repository', 'nix-purifiers/other'), ('reviewedRevision', self.main_revision)]:
            with self.subTest(key=key):
                self.write(self.variant / 'library.json', dict(self.library, **{key: value}))
                self.assert_rejected('reviewedRevision')

    def test_guide_must_be_the_reviewed_readme(self):
        (self.variant / 'reference.md').write_text('Unpaired branch guide\n')
        self.assert_rejected('must match the reviewed README.md')

    def test_missing_model_and_guide_are_rejected(self):
        model = self.variant / 'library.json'
        model.unlink()
        self.assert_rejected('requires library.json')
        self.write(model, self.library)
        (self.variant / 'reference.md').unlink()
        self.assert_rejected('requires reference.md')

    def test_library_scope_shape_is_validated(self):
        self.write(self.variant / 'library.json', dict(self.library, platforms='all'))
        self.assert_rejected('platforms')

    def test_library_variant_requires_model_mode(self):
        result, output = self.prepare(model=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('require --model', result.stderr)
        self.assertFalse(output.exists())
