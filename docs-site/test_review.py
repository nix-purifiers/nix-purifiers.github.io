import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from review import verify


class SourceReviewTests(unittest.TestCase):
    def test_code_changes_and_additions_require_review_but_workflow_edits_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', str(root)], check=True, capture_output=True)
            (root / 'tool.py').write_text('implementation\n')
            (root / '.github/workflows').mkdir(parents=True)
            workflow = root / '.github/workflows/pages.yml'
            workflow.write_text('old deployment\n')
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            manifest = {'example': {'repository': 'owner/example', 'revision': 'a' * 40,
                                   'files': {'tool.py': hashlib.sha256(b'implementation\n').hexdigest()}}}
            workflow.write_text('new deployment\n')
            self.assertEqual(verify('owner/example', root, manifest), 'a' * 40)
            ci = root / '.github/workflows/check.yml'
            ci.write_text('new platform validation\n')
            subprocess.run(['git', '-C', str(root), 'add', str(ci)], check=True)
            with self.assertRaisesRegex(ValueError, 'check.yml'):
                verify('owner/example', root, manifest)
            manifest['example']['files']['.github/workflows/check.yml'] = hashlib.sha256(ci.read_bytes()).hexdigest()
            (root / 'tool.py').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'needs source review'):
                verify('owner/example', root, manifest)
            (root / 'tool.py').write_text('implementation\n')
            (root / 'new.py').write_text('new behavior\n')
            subprocess.run(['git', '-C', str(root), 'add', 'new.py'], check=True)
            with self.assertRaisesRegex(ValueError, 'new.py'):
                verify('owner/example', root, manifest)
