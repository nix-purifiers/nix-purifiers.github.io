import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import xml.etree.ElementTree as ET

import packages
import publish
import repository


class ReleaseTests(unittest.TestCase):
    def test_exported_fixture_fingerprints_use_real_git_trees(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def git(*arguments):
                return subprocess.check_output(["git", *arguments], cwd=root, text=True).strip()

            git("init", "-q")
            git("config", "user.name", "Release fixture")
            git("config", "user.email", "fixture@example.invalid")
            git("config", "core.filemode", "true")
            fixtures = ("tests/python/native_composition.py", "tests/json-consumer.nix")
            files = (*fixtures, "tests/internal.py", "README.md", "docs/guide.md", "nix/lib/default.nix", "flake.lock")
            for name in files:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("original\n")
                path.chmod(0o644)
            git("add", ".")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            core = "nix-purifiers/purifier"
            other = "nix-purifiers/pip-purifier"
            original_core = publish.fingerprint(root, base, core)
            original_other = publish.fingerprint(root, base, other)
            self.assertEqual(original_other, publish.fingerprint(root, base))
            # The default/other-repository policy retains its exact old bytes.
            tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", base], cwd=root)
            included = [item for item in tree.split(b"\0") if item and
                        not item.split(b"\t", 1)[1].decode().startswith(("tests/", "docs/", ".github/")) and
                        item.split(b"\t", 1)[1].decode() not in ("README.md", ".gitignore")]
            self.assertEqual(original_other, hashlib.sha256(b"\0".join(included)).hexdigest())
            for name in fixtures:
                for change in ("blob", "mode", "delete"):
                    with self.subTest(path=name, change=change):
                        git("reset", "--hard", base)
                        path = root / name
                        if change == "blob":
                            path.write_text("changed\n")
                        elif change == "mode":
                            path.chmod(0o755)
                        else:
                            path.unlink()
                        git("add", "-A")
                        git("commit", "-qm", change)
                        self.assertNotEqual(publish.fingerprint(root, "HEAD", core), original_core)
                        self.assertEqual(publish.fingerprint(root, "HEAD", other), original_other)
                        self.assertEqual(publish.fingerprint(root, "HEAD"), original_other)
            for name in ("tests/internal.py", "README.md", "docs/guide.md", "nix/lib/default.nix", "flake.lock"):
                with self.subTest(path=name):
                    git("reset", "--hard", base)
                    (root / name).write_text("changed\n")
                    git("add", "-A")
                    git("commit", "-qm", "change")
                    production = name in ("nix/lib/default.nix", "flake.lock")
                    self.assertEqual(publish.fingerprint(root, "HEAD", core) == original_core, not production)
                    self.assertEqual(publish.fingerprint(root, "HEAD", other) == original_other, not production)

    def test_version_series_and_existing_tags(self):
        self.assertEqual(publish.next_version("0.1", ["v0.1.2", "v0.1.10", "v1.0.50", "notes"]), "0.1.11")
        self.assertEqual(publish.next_version("0.2", ["v0.1.10"]), "0.2.1")
        with self.assertRaises(ValueError):
            publish.next_version("main", [])

    def test_ci_gate_rejects_other_commits_and_pull_requests(self):
        with patch.object(publish, "api", return_value={"workflow_runs": [
            {"head_sha": "older", "head_branch": "main", "event": "push", "status": "completed", "conclusion": "success"},
            {"head_sha": "current", "head_branch": "main", "event": "pull_request", "status": "completed", "conclusion": "success"},
        ]}):
            self.assertFalse(publish.checked("owner/repo", "current"))
        with patch.object(publish, "api", return_value={"workflow_runs": [
            {"head_sha": "current", "head_branch": "main", "event": "push", "status": "completed", "conclusion": "success"}
        ]}):
            self.assertTrue(publish.checked("owner/repo", "current"))

    def test_ci_gate_does_not_depend_on_the_remote_status_index(self):
        success = {"head_sha": "current", "head_branch": "main", "event": "push",
                   "status": "completed", "conclusion": "success"}
        def response(repository, suffix):
            return {"workflow_runs": [] if "status=" in suffix else [success]}
        with patch.object(publish, "api", side_effect=response):
            self.assertTrue(publish.checked("owner/repo", "current"))

    def test_ci_gate_explicitly_rejects_unsuccessful_or_unfinished_runs(self):
        for status, conclusion in (("completed", "failure"), ("completed", "cancelled"),
                                   ("completed", "skipped"), ("in_progress", None),
                                   ("queued", None)):
            with self.subTest(status=status, conclusion=conclusion):
                run = {"head_sha": "current", "head_branch": "main", "event": "push",
                       "status": status, "conclusion": conclusion}
                with patch.object(publish, "api", return_value={"workflow_runs": [run]}):
                    self.assertFalse(publish.checked("owner/repo", "current"))

    def test_release_waits_for_exact_success_to_become_visible(self):
        success = {"head_sha": "current", "head_branch": "main", "event": "push",
                   "status": "completed", "conclusion": "success"}
        with patch.object(publish, "api", side_effect=[
            {"workflow_runs": []},
            {"workflow_runs": [dict(success, status="in_progress", conclusion=None)]},
            {"workflow_runs": [success]},
        ]) as query, patch.object(publish.time, "sleep") as sleep:
            self.assertTrue(publish.wait_for_checked("owner/repo", "current"))
            self.assertEqual(query.call_count, 3)
            self.assertEqual(sleep.call_count, 2)

    def test_release_visibility_wait_is_bounded_and_fails_closed(self):
        for fields in [dict(conclusion="failure"), dict(conclusion="cancelled"),
                       dict(conclusion="skipped"), dict(head_sha="other"),
                       dict(head_branch="topic"), dict(event="pull_request"),
                       dict(status="in_progress"), dict(status="queued")]:
            with self.subTest(fields=fields):
                observed = dict(head_sha="current", head_branch="main", event="push",
                                status="completed", conclusion="success")
                observed.update(fields)
                with patch.object(publish, "api", return_value={"workflow_runs": [observed]}) as query, \
                     patch.object(publish.time, "sleep") as sleep:
                    self.assertFalse(publish.wait_for_checked("owner/repo", "current"))
                    self.assertEqual(query.call_count, 6)
                    self.assertEqual(sleep.call_count, 5)
        with patch.object(publish, "api", return_value={"workflow_runs": []}) as query, \
             patch.object(publish.time, "sleep"):
            self.assertFalse(publish.wait_for_checked("owner/repo", "current"))
            self.assertEqual(query.call_count, 6)

    def test_visible_success_needs_no_wait(self):
        success = {"head_sha": "current", "head_branch": "main", "event": "push",
                   "status": "completed", "conclusion": "success"}
        with patch.object(publish, "api", return_value={"workflow_runs": [success]}) as query, \
             patch.object(publish.time, "sleep") as sleep:
            self.assertTrue(publish.wait_for_checked("owner/repo", "current"))
            query.assert_called_once()
            sleep.assert_not_called()

    def test_release_version_is_a_pure_override_of_a_locked_source(self):
        metadata = {"path": "/nix/store/fixture-source", "locked": {"narHash": "sha256-test+/="}}
        with patch.object(packages.subprocess, "check_output", side_effect=[
            json.dumps(metadata), json.dumps({"system": {"value": "x86_64-linux"}}), "/nix/store/released-extension\n"
        ]) as command:
            result = packages.nix_build(".#extension", version="0.1.123")
        self.assertEqual(result, Path("/nix/store/released-extension"))
        arguments = command.call_args_list[2].args[0]
        self.assertNotIn("--impure", arguments)
        expression = arguments[arguments.index("--expr") + 1]
        self.assertIn("narHash=sha256-test%2B%2F%3D", expression)
        self.assertIn('override { version = "0.1.123"; }', expression)
        self.assertNotIn("version.txt", expression)

    def test_maven_publication_does_not_modify_source_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            version_file = root / "version.txt"
            version_file.write_text("old-source-sentinel\n")
            extension = Path(temporary) / "extension/share/java"
            extension.mkdir(parents=True)
            (extension / "maven-purifier-extension.jar").write_bytes(b"native extension")
            destination = Path(temporary) / "release"
            destination.mkdir()
            with patch.object(packages, "nix_build", return_value=extension.parent.parent) as build:
                packages.build(root, "nix-purifiers/maven-purifier", "a" * 40,
                               "0.1.123", "maven", destination)
            build.assert_called_once_with(".#extension", version="0.1.123")
            self.assertEqual(version_file.read_text(), "old-source-sentinel\n")
            with zipfile.ZipFile(destination / "native-repository.zip") as archive:
                pom = next(name for name in archive.namelist() if name.endswith(".pom"))
                self.assertEqual(ET.fromstring(archive.read(pom)).find("{*}version").text, "0.1.123")

    def test_python_index_retains_versions_with_exact_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            project = site / "simple/poetry-purifier"
            project.mkdir(parents=True)
            for version in ("0.1.1", "0.1.2"):
                (project / f"poetry_purifier-{version}-py3-none-any.whl").write_bytes(version.encode())
            repository.indexes(site)
            text = (project / "index.html").read_text()
            for version in ("0.1.1", "0.1.2"):
                self.assertIn(hashlib.sha256(version.encode()).hexdigest(), text)
                self.assertIn(version, text)

    def test_yarn_latest_is_numeric_and_old_versions_remain(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            for version in ("0.1.9", "0.1.10"):
                path = site / "plugins" / version
                path.mkdir(parents=True)
                (path / "purifier.cjs").write_text(version)
            repository.indexes(site)
            self.assertEqual((site / "plugins/purifier.cjs").read_text(), "0.1.10")
            self.assertTrue((site / "plugins/0.1.9/purifier.cjs").exists())
            self.assertIn("0.1.10/", (site / "plugins/index.html").read_text())

    def test_maven_metadata_keeps_all_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            artifact = site / "maven/io/github/nix-purifiers/maven-purifier-extension"
            for version in ("0.1.2", "0.1.10"):
                (artifact / version).mkdir(parents=True)
            repository.indexes(site)
            text = (artifact / "maven-metadata.xml").read_text()
            self.assertIn("<latest>0.1.10</latest>", text)
            self.assertIn("<version>0.1.2</version>", text)
            self.assertTrue((artifact / "maven-metadata.xml.sha256").exists())
            self.assertIn("io/", (site / "maven/index.html").read_text())
            repository.indexes(site)
            self.assertIn("<latest>0.1.10</latest>", (artifact / "maven-metadata.xml").read_text())

    def test_ant_plugin_release_is_consumable_and_retains_previous_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin/share/java"
            plugin.mkdir(parents=True)
            with zipfile.ZipFile(plugin / "ant-purifier.jar", "w") as jar:
                jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
                jar.writestr("org/nixpurifiers/ant/antlib.xml", '<antlib/>')
            site = root / "site"
            expected = (plugin / "ant-purifier.jar").read_bytes()
            for version in ("0.1.1", "0.1.2"):
                destination = root / version
                destination.mkdir()
                with patch.object(packages, "nix_build", return_value=plugin.parent.parent):
                    packages.build(root, "nix-purifiers/ant-purifier", "fixture", version, "ant", destination)
                repository.extract(destination / "native-repository.zip", site)
            repository.indexes(site)
            project = site / "maven/io/github/nix-purifiers/ant-purifier"
            for version in ("0.1.1", "0.1.2"):
                jar = project / version / f"ant-purifier-{version}.jar"
                with zipfile.ZipFile(jar) as published, zipfile.ZipFile(io.BytesIO(expected)) as original:
                    for entry in original.namelist():
                        self.assertEqual(published.read(entry), original.read(entry))
                    self.assertEqual(published.read("org/nixpurifiers/ant/release.properties").decode(),
                                     "reference=github:nix-purifiers/ant-purifier/fixture\n")
                self.assertEqual(jar.with_suffix(".jar.sha256").read_text().strip(), hashlib.sha256(jar.read_bytes()).hexdigest())
                pom = ET.parse(jar.with_suffix(".pom")).getroot()
                ns = {"m": "http://maven.apache.org/POM/4.0.0"}
                self.assertEqual(pom.findtext("m:groupId", namespaces=ns), "io.github.nix-purifiers")
                self.assertEqual(pom.findtext("m:artifactId", namespaces=ns), "ant-purifier")
                self.assertEqual(pom.findtext("m:version", namespaces=ns), version)
            self.assertIn("<latest>0.1.2</latest>", (project / "maven-metadata.xml").read_text())
            self.assertIn("<version>0.1.1</version>", (project / "maven-metadata.xml").read_text())

    def test_release_archive_cannot_escape_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "evil.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("../escape", "bad")
            with self.assertRaises(ValueError):
                repository.extract(archive, Path(temporary) / "site")

    def test_published_poetry_plugin_uses_its_exact_commit(self):
        namespace = {}
        exec(packages.poetry_bootstrap("nix-purifiers/poetry-purifier", "abc123"), namespace)
        runtime = {"realize": "/nix/store/realize", "build": "/nix/store/build", "path": "/nix/store/git/bin"}
        with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            with patch("subprocess.check_output", side_effect=["/nix/store/wrapper\n", json.dumps(runtime)]) as command:
                namespace["configure"]()
                self.assertIn("/abc123#poetry", command.call_args_list[0].args[0][-1])
                self.assertEqual(os.environ["POETRY_PURIFIER_REALIZE"], runtime["realize"])
                self.assertIn(runtime["path"], os.environ["PATH"])
                namespace["configure"]()
                self.assertEqual(command.call_count, 2)
        with patch.dict(os.environ, {"POETRY_PURIFIER_MODE": "record"}, clear=True), patch("subprocess.check_output") as command:
            namespace["configure"]()
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
