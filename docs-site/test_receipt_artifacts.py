from pathlib import Path
import tempfile
import unittest
from receipt_artifacts import retain, verify_local


class ReceiptArtifactTests(unittest.TestCase):
    def test_retains_exact_bytes_and_verifies_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'captured.json'
            raw = b'{"capturedCommand":"nix build", "exampleOnly":true}\n'
            source.write_bytes(raw)
            destination = root / 'public'
            base = 'https://example.test/receipts/'
            reference = retain(source, destination, base)
            self.assertEqual(retain(source, destination, base), reference)
            self.assertEqual((destination / (reference['artifactSha256'] + '.json')).read_bytes(), raw)
            self.assertTrue(verify_local(destination, base, reference)['exampleOnly'])
            self.assertNotIn('artifactSha256', source.read_text())
            for changed in (dict(reference, receipt=base + '../captured.json'),
                            dict(reference, artifactSha256='a' * 64)):
                with self.assertRaises(ValueError):
                    verify_local(destination, base, changed)
            (destination / (reference['artifactSha256'] + '.json')).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'bytes'):
                verify_local(destination, base, reference)

    def test_requires_actual_json_and_explicit_canonical_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'receipt'
            source.write_text('not a receipt')
            with self.assertRaises(ValueError):
                retain(source, Path(directory) / 'out', 'https://example.test/receipts')
            source.write_text('{}')
            for base in ('http://example.test/x', 'https://example.test/x?token=y',
                         'https://example.test/../x', 'https://example.test/%2e%2e/x'):
                with self.assertRaises(ValueError):
                    retain(source, Path(directory) / 'out', base)
