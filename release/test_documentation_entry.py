import tempfile
from pathlib import Path
import unittest

from documentation_entry import write_entries


class NativeDocumentationRouting(unittest.TestCase):
    def test_native_payload_and_sidecars_survive_idempotent_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            native = site / 'maven/io/github/nix-purifiers/plugin/1.0/plugin.jar'
            native.parent.mkdir(parents=True)
            native.write_bytes(b'published-native-package\x00')
            sidecar = native.with_suffix('.jar.sha256')
            sidecar.write_text('retained checksum\n')
            index = native.parent / 'index.html'
            index.write_text('<a href="plugin.jar">plugin</a>')
            before = {str(p.relative_to(site)): (p.read_bytes(), p.stat().st_mode)
                      for p in site.rglob('*') if p.is_file()}
            write_entries('nix-purifiers/maven-purifier', site)
            after = {str(p.relative_to(site)): p.read_bytes()
                     for p in site.rglob('*') if p.is_file()}
            self.assertEqual(set(after), set(before) | {'index.html', 'reference.html', 'features.html'})
            for path, (content, mode) in before.items():
                self.assertEqual((site / path).read_bytes(), content)
                self.assertEqual((site / path).stat().st_mode, mode)
            for page in ['index.html', 'reference.html', 'features.html']:
                html = (site / page).read_text()
                self.assertIn('https://nix-purifiers.github.io/projects/maven-purifier/', html)
                self.assertIn('location.search+location.hash', html)
                self.assertNotIn('Tier ', html)
            write_entries('nix-purifiers/maven-purifier', site)
            self.assertEqual(after, {str(p.relative_to(site)): p.read_bytes()
                                    for p in site.rglob('*') if p.is_file()})

    def test_repository_cannot_escape_output_or_inject_markup(self):
        with tempfile.TemporaryDirectory() as directory:
            for repository in ['other-owner/maven-purifier', 'nix-purifiers/../maven',
                               'nix-purifiers/x"><script>']:
                with self.subTest(repository=repository), self.assertRaises(ValueError):
                    write_entries(repository, Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
