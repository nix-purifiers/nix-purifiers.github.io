"""Canonical documentation does not depend on independent project Pages builds."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from functools import lru_cache
import runpy
import quality

from authority import canonicalize, entry, project_root, validate_inputs


class AuthorityTests(unittest.TestCase):
    def test_rewrites_only_documentation_links_and_is_idempotent(self):
        text = ('<a href="/sbt-purifier/">SBT</a> '
                '[Guide](https://nix-purifiers.github.io/sbt-purifier/reference.html#editor) '
                '[Maven](https://nix-purifiers.github.io/sbt-purifier/maven/org/example) '
                '`https://nix-purifiers.github.io/sbt-purifier/` '
                '[Source](https://github.com/nix-purifiers/sbt-purifier/)')
        result = canonicalize(text, ['sbt-purifier'])
        self.assertIn('href="/projects/sbt-purifier/"', result)
        self.assertIn('/projects/sbt-purifier/reference.html#editor', result)
        self.assertIn('/sbt-purifier/maven/org/example', result)
        self.assertIn('`https://nix-purifiers.github.io/sbt-purifier/`', result)
        self.assertIn('https://github.com/nix-purifiers/sbt-purifier/', result)
        self.assertEqual(canonicalize(result, ['sbt-purifier']), result)

    def test_legacy_fragment_entries_ignore_fenced_comments(self):
        text = entry('nix-purifiers/uv-purifier', 'reference.html', reference=(
            '## Setup\n\n```sh\n# not a heading\n```\n\n<a id="old-setup"></a>\n'))
        self.assertIn('reference.html#setup', text)
        self.assertIn('reference.html#old-setup', text)
        self.assertNotIn('#not-a-heading', text)
        self.assertNotIn('```', text)

    def test_central_input_manifest_rejects_missing_or_relabelled_context(self):
        documentation = json.loads((Path(__file__).resolve().parent / 'catalog.json').read_text())
        validate_inputs(documentation)
        altered = copy.deepcopy(documentation)
        altered['catalog'].pop('uv-purifier')
        with self.assertRaisesRegex(ValueError, 'complete pinned source manifest'):
            validate_inputs(altered)
        documentation['catalog']['uv-purifier']['reviewedRevision'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'pinned source identity'):
            validate_inputs(documentation)

    def test_all_85_poisoned_local_snapshots_only_emit_canonical_entries(self):
        theme = Path(__file__).resolve().parent
        documentation = json.loads((theme / 'catalog.json').read_text())
        self.assertEqual(len(documentation['catalog']), 85)
        # Reuse one validated immutable registry across the 85 isolated script
        # executions; revalidating the same native evidence 170 times obscures
        # the authority boundary this regression test exercises.
        cached_registry = lru_cache(maxsize=1)(quality.registry)
        with tempfile.TemporaryDirectory() as temporary, patch('quality.registry', cached_registry), patch('theme.registry', cached_registry):
            root = Path(temporary)
            for name, original in documentation['catalog'].items():
                with self.subTest(name=name):
                    page = copy.deepcopy(original)
                    page['facts']['editor_diagnostics'] = {
                        'state': 'unknown', 'reason': 'POISONED_LOCAL_FEATURE_CLAIM'}
                    page['quality']['tier'] = 1  # Never a current-rank authority.
                    content = root / 'page.json'
                    content.write_text(json.dumps(page))
                    out = root / 'site'
                    package = out / 'maven' / 'plugin.jar'
                    package.parent.mkdir(parents=True, exist_ok=True)
                    package.write_bytes(b'preserved native payload')
                    with patch.object(sys, 'argv', [str(theme / 'prepare.py'),
                        '--repository', page['repository'], '--content', str(content),
                        '--output', str(out)]):
                        runpy.run_path(str(theme / 'prepare.py'))
                    for filename in ('index.md', 'reference.md', 'features.md'):
                        text = (out / filename).read_text()
                        self.assertIn('https://nix-purifiers.github.io' + project_root(page['repository']), text)
                        self.assertNotIn('POISONED_LOCAL_FEATURE_CLAIM', text)
                        self.assertNotIn('| Feature |', text)
                        self.assertNotRegex(text, r'Tier [1-4]')
                    config = json.loads((out / '_config.yml').read_text())
                    self.assertFalse(config['central_documentation'])
                    self.assertEqual(config['documentation_roots'][page['repository']],
                        'https://nix-purifiers.github.io' + project_root(page['repository']))
                    snapshot = json.loads((out / 'system.json').read_text())
                    self.assertEqual(snapshot['facts']['editor_diagnostics']['reason'], 'POISONED_LOCAL_FEATURE_CLAIM')
                    self.assertIn('reviewedRevision', snapshot)
                    self.assertEqual(package.read_bytes(), b'preserved native payload')
