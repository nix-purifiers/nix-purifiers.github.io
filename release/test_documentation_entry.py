import tempfile
from pathlib import Path
import unittest

from documentation_entry import write_entries


class NativeDocumentationRouting(unittest.TestCase):
    def test_late_protected_collision_prevents_all_alias_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            protected = site / 'features.html'
            protected.write_bytes(b'protected native publisher output')
            with self.assertRaises(ValueError):
                write_entries('nix-purifiers/maven-purifier', site)
            self.assertEqual(list(site.iterdir()), [protected])
            self.assertEqual(protected.read_bytes(), b'protected native publisher output')

    def test_symlink_and_nonregular_collision_prevent_all_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            native = parent / 'native.jar'
            native.write_bytes(b'protected package')
            for kind in ['symlink', 'dangling-symlink', 'directory']:
                site = parent / kind
                site.mkdir()
                target = site / 'reference.html'
                if kind == 'directory':
                    target.mkdir()
                else:
                    target.symlink_to(native if kind == 'symlink' else parent / 'missing')
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    write_entries('nix-purifiers/maven-purifier', site)
                self.assertFalse((site / 'index.html').exists())
                self.assertFalse((site / 'features.html').exists())
                self.assertEqual(native.read_bytes(), b'protected package')

    def test_symlink_publication_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            actual = parent / 'actual'
            actual.mkdir()
            link = parent / 'site'
            link.symlink_to(actual, target_is_directory=True)
            with self.assertRaises(ValueError):
                write_entries('nix-purifiers/maven-purifier', link)
            self.assertEqual(list(actual.iterdir()), [])

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
