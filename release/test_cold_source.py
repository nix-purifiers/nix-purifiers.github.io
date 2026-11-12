"""Cold source snapshots, pure overrides and owned build-root lifetimes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import uuid

import packages


class BuildFailureTests(unittest.TestCase):
    def test_changed_snapshot_fails_closed_and_removes_only_owned_temporary_links(self):
        with tempfile.TemporaryDirectory() as fixture:
            sentinel = Path(fixture) / "version.txt"
            sentinel.write_text("unchanged-source-version\n")
            owned = tempfile.TemporaryDirectory(dir=fixture, prefix="owned-")
            location = Path(owned.name)
            metadata = {"path": "/absent/promised-source", "locked": {"narHash": "sha256-captured"}}
            with patch.object(packages.tempfile, "TemporaryDirectory", return_value=owned), \
                 patch.object(packages.subprocess, "check_output", side_effect=[
                     json.dumps(metadata), json.dumps({"path": "/materialized/source"}), "sha256-changed\n"
                 ]) as command, patch.object(packages.atexit, "register") as cleanup:
                with self.assertRaisesRegex(RuntimeError, "source changed"):
                    packages.nix_build(".#extension", version="0.1.123")
            self.assertFalse(location.exists())
            self.assertEqual(sentinel.read_text(), "unchanged-source-version\n")
            cleanup.assert_not_called()
            self.assertFalse(any(c.args[0][:2] == ["nix", "build"] for c in command.call_args_list))

    def test_failed_pure_build_releases_owned_links_without_gc_or_fallback(self):
        with tempfile.TemporaryDirectory() as fixture:
            owned = tempfile.TemporaryDirectory(dir=fixture, prefix="owned-")
            location = Path(owned.name)
            metadata = {"path": "/absent/promised-source", "locked": {"narHash": "sha256-captured"}}
            with patch.object(packages.tempfile, "TemporaryDirectory", return_value=owned), \
                 patch.object(packages.subprocess, "check_output", side_effect=[
                     json.dumps(metadata), json.dumps({"path": "/materialized/source"}),
                     "sha256-captured\n", str(location / "source") + "\n",
                     json.dumps({"system": {"value": "selected-system"}}),
                     subprocess.CalledProcessError(1, ["nix", "build"])
                 ]) as command, patch.object(packages.atexit, "register") as cleanup:
                with self.assertRaises(subprocess.CalledProcessError):
                    packages.nix_build(".#plugin^dist", version="0.1.123")
            self.assertFalse(location.exists())
            cleanup.assert_not_called()
            builds = [c.args[0] for c in command.call_args_list if c.args[0][:2] == ["nix", "build"]]
            self.assertEqual(len(builds), 1)
            self.assertNotIn("--impure", builds[0])
            self.assertIn('packages."selected-system".plugin', builds[0][-1])
            self.assertIn('version = "0.1.123"', builds[0][-1])
            for call in command.call_args_list:
                self.assertNotIn("--gc", call.args[0])
                self.assertNotIn("--delete", call.args[0])


@unittest.skipUnless(shutil.which("nix") and shutil.which("nix-store") and shutil.which("git"),
                     "real Nix and Git are required for cold snapshot integration")
class ColdSourceTests(unittest.TestCase):
    def assert_registered_indirect_root(self, link):
        # Inspect just this daemon-created back-reference. A global --query
        # --roots scan also prunes unrelated stale roots and is not read-only.
        digest = hashlib.sha1(os.fsencode(link)).digest()
        alphabet = "0123456789abcdfghijklmnpqrsvwxyz"
        number = int.from_bytes(digest, "little")
        name = "".join(alphabet[(number >> (i * 5)) & 31]
                       for i in reversed(range((len(digest) * 8 + 4) // 5)))
        state = Path(os.environ.get("NIX_STATE_DIR", "/nix/var/nix"))
        registration = state / "gcroots/auto" / name
        self.assertTrue(link.is_symlink())
        self.assertTrue(registration.is_symlink(), str(registration))
        self.assertEqual(Path(os.readlink(registration)), link)

    def exercise_snapshot(self, git):
        with tempfile.TemporaryDirectory(prefix="publisher-cold-source-test-") as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            source.mkdir()
            marker = uuid.uuid4().hex
            (source / "proof.txt").write_text(marker)
            (source / "flake.nix").write_text('''{
  outputs = { self }: {
    proof = builtins.readFile ./proof.txt;
    bootstrap = builtins.readFile ./src/poetry_purifier/_release.py;
  };
}
''')
            (source / "flake.lock").write_text(json.dumps({
                "nodes": {"root": {"inputs": {}}}, "root": "root", "version": 7
            }))
            bootstrap = packages.poetry_bootstrap("nix-purifiers/poetry-purifier", "a" * 40)
            if git:
                def command(*arguments):
                    return subprocess.check_output(["git", *arguments], cwd=source, text=True).strip()
                command("init", "-q")
                command("config", "user.name", "Cold publisher fixture")
                command("config", "user.email", "fixture@example.invalid")
                command("add", ".")
                command("commit", "-qm", "unique cold source")
            generated = source / "src/poetry_purifier/_release.py"
            generated.parent.mkdir(parents=True)
            generated.write_text(bootstrap)
            if git:
                command("add", "--intent-to-add", "src/poetry_purifier/_release.py")
            roots = root / "roots"
            roots.mkdir()
            reference = "git+" + source.as_uri() if git else "path:" + str(source)
            metadata = {}
            real = subprocess.check_output

            def observe(arguments, **kwargs):
                result = real(arguments, **kwargs)
                if arguments[:3] == ["nix", "flake", "metadata"]:
                    metadata.update(json.loads(result))
                return result

            with patch.object(packages.subprocess, "check_output", side_effect=observe):
                locked = packages._locked_source(reference, roots)
            captured = Path(metadata["path"])
            self.assertTrue(captured.is_dir())
            self.assert_registered_indirect_root(roots / "source")
            self.assertEqual(parse_qs(urlsplit(locked).query)["narHash"],
                             [metadata["locked"]["narHash"]])
            self.assertEqual((captured / "src/poetry_purifier/_release.py").read_text(), bootstrap)
            # A subsequent checkout edit must not affect the captured source.
            (source / "proof.txt").write_text("changed after snapshot")
            expression = "(builtins.getFlake " + json.dumps(locked) + ").proof"
            result = real(["nix", "eval", "--raw", "--expr", expression], text=True)
            self.assertEqual(result, marker)
            expression = "(builtins.getFlake " + json.dumps(locked) + ").bootstrap"
            self.assertEqual(real(["nix", "eval", "--raw", "--expr", expression], text=True), bootstrap)

    def test_cold_plain_source_is_materialized_hash_bound_and_rooted(self):
        self.exercise_snapshot(git=False)

    def test_cold_git_source_includes_intent_to_add_poetry_bootstrap(self):
        self.exercise_snapshot(git=True)


if __name__ == "__main__":
    unittest.main()
