import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from testing import build_testing


class TestingPublicationTests(unittest.TestCase):
    def setUp(self):
        self.plan = {'projects': {'maven': {'obligations': [
            {'id': 'sandwich', 'applicability': 'required'}]}}, 'projectionCandidates': []}
        encoded = json.dumps(self.plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        self.evidence = {'planDigest': hashlib.sha256(encoded).hexdigest(), 'projects': {
            'maven': {'contexts': [{'obligations': {'sandwich': {'origin': 'passed', 'runtime': 'not-run'}}}]}}}

    def test_partial_observations_are_published_without_claiming_full_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_testing(self.plan, self.evidence, root)
            text = (root / 'testing/index.md').read_text()
            self.assertIn('partial execution', text)
            self.assertIn('| [maven](projects/maven.html) | 1 | 0 | 1 | 1 |', text)
            detail = (root / 'testing/projects/maven.md').read_text()
            self.assertIn('| sandwich | origin | passed |', detail)
            self.assertIn('| sandwich | runtime | not run |', detail)
            self.assertIn('Download project data (JSON)', detail)
            self.assertIn('<details markdown="1">', text)
            self.assertNotIn('[Full plan]', text)
            exported = json.loads((root / 'testing/projects/maven.json').read_text())
            self.assertEqual(exported['execution'], self.evidence['projects']['maven'])
            build_testing(self.plan, None, root)
            self.assertFalse((root / 'testing/audit.json').exists())
            self.assertIn('No execution evidence', (root / 'testing/index.md').read_text())
            build_testing(dict(self.plan, projects={}), None, root)
            self.assertFalse((root / 'testing/projects/maven.json').exists())
            self.assertFalse((root / 'testing/projects/maven.md').exists())

    def test_stale_or_incomplete_audit_fails_before_publishing(self):
        for evidence in (dict(self.evidence, planDigest='stale'), dict(self.evidence, projects={})):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(ValueError):
                    build_testing(self.plan, evidence, root)
                self.assertFalse((root / 'testing').exists())


if __name__ == '__main__':
    unittest.main()
