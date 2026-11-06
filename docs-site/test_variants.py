import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import re

from content import render
from reference import guide_plan
from review import validate_library


class PublishedReviewTests(unittest.TestCase):
    def test_every_committed_variant_has_a_valid_paired_model_and_guide(self):
        theme = Path(__file__).resolve().parent
        documentation = json.loads((theme / 'catalog.json').read_text())
        fingerprints = set()
        for source in sorted((theme / 'reviews').glob('*/*/source.json')):
            with self.subTest(source=source):
                record = json.loads(source.read_text())
                self.assertEqual(set(record), {'repository', 'revision', 'files'})
                self.assertRegex(record['revision'], r'^[a-f0-9]{40}$')
                self.assertEqual(record['repository'], 'nix-purifiers/' + source.parent.parent.name)
                if record['repository'] != 'nix-purifiers/purifier':
                    self.assertIn(source.parent.parent.name, documentation['catalog'])
                self.assertTrue(record['files'])
                for path, digest in record['files'].items():
                    self.assertFalse(Path(path).is_absolute() or '..' in Path(path).parts)
                    self.assertTrue(re.fullmatch(r'[a-f0-9]{64}', digest))
                identity = record['repository'], json.dumps(record['files'], sort_keys=True)
                self.assertNotIn(identity, fingerprints)
                fingerprints.add(identity)
                if record['repository'] == 'nix-purifiers/purifier':
                    validate_library(json.loads((source.parent / 'library.json').read_text()),
                                     record['repository'], record['revision'])
                    self.assertEqual(hashlib.sha256((source.parent / 'reference.md').read_bytes()).hexdigest(),
                                     record['files']['README.md'])
                    continue
                page = json.loads((source.parent / 'page.json').read_text())
                self.assertEqual(page['repository'], record['repository'])
                self.assertEqual(page['reviewedRevision'], record['revision'])
                render(page, documentation['contract'])
                plan_file = source.parent / 'guide.json'
                plan = json.loads(plan_file.read_text()) if plan_file.exists() else None
                guide_plan(record['repository'], (source.parent / 'reference.md').read_text(), plan)


class ReviewedVariantTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        original = Path(__file__).resolve().parent
        self.site = root / 'site'
        shutil.copytree(original, self.site / 'docs-site', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(original.parent / 'index.html', self.site / 'index.html')
        shutil.copyfile(original.parent / 'robots.txt', self.site / 'robots.txt')
        (self.site / 'model').mkdir()
        shutil.copyfile(original.parent / 'model/tiers.json', self.site / 'model/tiers.json')
        self.checkout = root / 'checkout'
        self.checkout.mkdir()
        subprocess.run(['git', 'init', str(self.checkout)], check=True, capture_output=True)
        (self.checkout / 'tool.py').write_text('main implementation\n')
        subprocess.run(['git', '-C', str(self.checkout), 'add', '.'], check=True)
        self.repository = 'nix-purifiers/bun-purifier'
        self.main_revision = 'a' * 40
        self.branch_revision = 'b' * 40
        manifest = {'bun-purifier': self.record(self.main_revision)}
        (self.site / 'model/repositories.json').write_text(json.dumps(manifest))
        self.catalog = self.site / 'docs-site/catalog.json'
        documentation = json.loads(self.catalog.read_text())
        self.main_page = documentation['catalog']['bun-purifier']
        self.main_page['reviewedRevision'] = self.main_revision
        self.catalog.write_text(json.dumps(documentation))
        self.catalog_before = self.catalog.read_bytes()
        (self.checkout / 'tool.py').write_text('reviewed branch implementation\n')
        self.variant = self.site / 'docs-site/reviews/bun-purifier' / self.branch_revision
        self.variant.mkdir(parents=True)
        (self.variant / 'source.json').write_text(json.dumps(self.record(self.branch_revision)))
        self.branch_page = copy.deepcopy(self.main_page)
        self.branch_page['reviewedRevision'] = self.branch_revision
        self.branch_page['summary'] = 'Explicitly reviewed branch behavior.'
        self.branch_page['facts']['dependency_sources'] = {
            'state': 'known', 'value': ['reviewed branch repository'],
            'sources': ['tool.py'],
        }
        (self.variant / 'page.json').write_text(json.dumps(self.branch_page))
        guide = (self.site / 'docs-site/references/bun-purifier.md').read_text()
        (self.variant / 'reference.md').write_text(guide + '\nReviewed branch guide: [source](tool.py).\n')

    def record(self, revision):
        return {'repository': self.repository, 'revision': revision,
                'files': {'tool.py': hashlib.sha256((self.checkout / 'tool.py').read_bytes()).hexdigest()}}

    def prepare(self, output, check=True):
        arguments = [sys.executable, str(self.site / 'docs-site/prepare.py'),
                     '--repository', self.repository, '--model', '--output', str(output)]
        if check:
            arguments += ['--check-source', str(self.checkout)]
        return subprocess.run(arguments, text=True, capture_output=True)

    def test_matching_branch_uses_its_model_and_guide_without_changing_main(self):
        output = Path(self.temporary.name) / 'branch'
        result = self.prepare(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((output / 'system.json').read_text()), self.branch_page)
        self.assertIn('Explicitly reviewed branch behavior.', (output / 'index.md').read_text())
        self.assertIn('reviewed branch repository', (output / 'features.md').read_text())
        self.assertIn('Reviewed branch guide', (output / 'reference.md').read_text())
        self.assertIn('/blob/' + self.branch_revision + '/tool.py', (output / 'reference.md').read_text())
        canonical = Path(self.temporary.name) / 'canonical'
        result = self.prepare(canonical, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((canonical / 'system.json').read_text()), self.main_page)
        self.assertEqual(self.catalog.read_bytes(), self.catalog_before)

    def test_old_source_snapshot_uses_current_orthogonal_quality_metadata(self):
        self.branch_page.pop('quality', None)
        (self.variant / 'page.json').write_text(json.dumps(self.branch_page))
        output = Path(self.temporary.name) / 'old-quality-output'
        result = self.prepare(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        exported = json.loads((output / 'system.json').read_text())
        tiers = json.loads((self.site / 'model/tiers.json').read_text())
        self.assertEqual(exported['quality'], tiers['projects']['bun-purifier'])
        self.assertEqual(exported['reviewedRevision'], self.branch_revision)
        self.assertEqual(exported['summary'], 'Explicitly reviewed branch behavior.')

    def test_unreviewed_changes_are_rejected_before_output(self):
        (self.checkout / 'tool.py').write_text('unreviewed implementation\n')
        output = Path(self.temporary.name) / 'unreviewed'
        result = self.prepare(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('needs source review', result.stderr)
        self.assertFalse(output.exists())

    def test_variant_cannot_pair_a_source_review_with_another_model_revision(self):
        self.branch_page['reviewedRevision'] = self.main_revision
        (self.variant / 'page.json').write_text(json.dumps(self.branch_page))
        output = Path(self.temporary.name) / 'mismatched'
        result = self.prepare(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('reviewedRevision', result.stderr)
        self.assertFalse(output.exists())

    def test_workflow_only_change_keeps_reviewed_branch_selection(self):
        workflow = self.checkout / '.github/workflows/pages.yml'
        workflow.parent.mkdir(parents=True)
        workflow.write_text('changed theme pin\n')
        subprocess.run(['git', '-C', str(self.checkout), 'add', '.'], check=True)
        output = Path(self.temporary.name) / 'workflow'
        result = self.prepare(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((output / 'system.json').read_text()), self.branch_page)

    def test_source_review_requires_its_guide(self):
        (self.variant / 'reference.md').unlink()
        output = Path(self.temporary.name) / 'missing-guide'
        result = self.prepare(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires reference.md', result.stderr)
        self.assertFalse(output.exists())

    def test_ambiguous_source_reviews_are_rejected(self):
        shutil.copytree(self.variant, self.variant.parent / 'duplicate')
        output = Path(self.temporary.name) / 'ambiguous'
        result = self.prepare(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('multiple reviewed variants', result.stderr)
        self.assertFalse(output.exists())

    def test_branch_guide_sections_require_their_own_explicit_plan(self):
        reference = self.variant / 'reference.md'
        reference.write_text(reference.read_text() + '\n## New branch feature\n\nNative branch details.\n')
        output = Path(self.temporary.name) / 'new-guide'
        result = self.prepare(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('assigned exactly once', result.stderr)
        plan_file = self.site / 'docs-site/guides/bun-purifier.json'
        canonical = plan_file.read_bytes()
        plan = json.loads(canonical)
        plan['sections']['projections']['sourceSections'].append('New branch feature')
        (self.variant / 'guide.json').write_text(json.dumps(plan))
        result = self.prepare(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Native branch details.', (output / 'reference.md').read_text())
        self.assertEqual(plan_file.read_bytes(), canonical)
