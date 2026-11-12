import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

import packages


class YarnPublicationTests(unittest.TestCase):
    repository = "nix-purifiers/yarn-berry-purifier"
    revision = "a" * 40

    def source(self, root, owner):
        (root / "plugin").mkdir(parents=True)
        (root / "plugin/purifier.cjs").write_text(
            'const childProcess=require("child_process"); const path=require("path");\n'
            'const foreign = require("./foreign.cjs");\n'
            'const NIX_LIB = "@nixLib@"; const NIXPKGS = "@nixpkgs@"; '
            'const FLAKE = "@flake@";\n'
        )
        (root / "plugin/foreign.cjs").write_text("module.exports = {};\n")
        directory = root / owner
        directory.mkdir(parents=True)
        for entry in ("interactive.nix", "publish.nix", "release.nix"):
            (directory / entry).write_text("producer-owned " + entry + "\n")

    def test_generated_plugin_loads_complete_exact_producer_for_both_layouts(self):
        if shutil.which("node") is None:
            self.fail("Node is required to execute the published Yarn plugin")
        for owner in ("nix/lib", "pkgs/plugin"):
            with self.subTest(owner=owner), tempfile.TemporaryDirectory(prefix="yarn publication ") as temporary:
                work = Path(temporary)
                root = work / "release source"
                self.source(root, owner)
                producer = work / "producer package"
                producer.mkdir()
                # Loading the producer also needs a sibling resource. The
                # published entry must preserve the producer's module closure.
                (producer / "inputs.cjs").write_text('module.exports = "producer inputs";\n')
                (producer / "purifier.cjs").write_text(
                    'const fs=require("fs"); const inputs=require("./inputs.cjs");\n'
                    'module.exports={name:"fixture", factory:()=>inputs, '
                    'runtime:fs.readFileSync(' + json.dumps(str(root / owner / "interactive.nix")) + ',"utf8")};\n'
                )
                reference = f"github:{self.repository}/{self.revision}"
                commands = work / "commands.jsonl"
                tools = work / "bin"
                tools.mkdir()
                nix = tools / "nix"
                nix.write_text(
                    "#!" + sys.executable + "\n"
                    "import json,sys\n"
                    "args=sys.argv[1:]\n"
                    "with open(" + repr(str(commands)) + ", 'a') as stream: stream.write(json.dumps(args)+'\\n')\n"
                    "if args==['flake','metadata','--json','--no-update-lock-file'," + repr(reference) + "]:\n"
                    " print(json.dumps({'path':" + repr(str(root)) + "}))\n"
                    "elif args==['build','--no-link','--print-out-paths','--no-update-lock-file'," + repr(reference + "#plugin") + "]:\n"
                    " print(" + repr(str(producer)) + ")\n"
                    "else: raise SystemExit('unexpected unpinned Nix command: '+repr(args))\n"
                )
                nix.chmod(0o755)
                native = work / "published.cjs"
                native.write_text(packages.yarn_plugin(root, self.repository, self.revision))
                result = subprocess.run(
                    ["node", "-e", "const p=require(process.argv[1]); console.log(JSON.stringify({name:p.name,inputs:p.factory(),runtime:p.runtime}));", str(native)],
                    env=dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"]),
                    text=True, capture_output=True, check=True,
                )
                self.assertEqual(json.loads(result.stdout), {
                    "name": "fixture", "inputs": "producer inputs", "runtime": "producer-owned interactive.nix\n",
                })
                calls = [json.loads(line) for line in commands.read_text().splitlines()]
                self.assertEqual(calls, [
                    ["flake", "metadata", "--json", "--no-update-lock-file", reference],
                    ["build", "--no-link", "--print-out-paths", "--no-update-lock-file", reference + "#plugin"],
                ])
                # This is a command-boundary fixture, not native SDK evidence.
                # The separate integration receipt uses real producer outputs.

    def test_missing_or_ambiguous_runtime_sources_fail_before_publication(self):
        for mode in ("missing", "partial", "ambiguous"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.source(root, "nix/lib")
                if mode == "missing":
                    shutil.rmtree(root / "nix")
                elif mode == "partial":
                    (root / "nix/lib/publish.nix").unlink()
                else:
                    (root / "pkgs/plugin").mkdir(parents=True)
                    for entry in ("interactive.nix", "publish.nix", "release.nix"):
                        (root / "pkgs/plugin" / entry).write_text("another owner\n")
                with self.assertRaisesRegex(ValueError, "runtime"):
                    packages.yarn_plugin(root, self.repository, self.revision)

    def test_native_archive_preserves_its_versioned_public_entry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            self.source(root, "pkgs/plugin")
            destination = Path(temporary) / "release"
            destination.mkdir()
            packages.build(root, self.repository, self.revision, "0.1.9", "yarn", destination)
            with zipfile.ZipFile(destination / "native-repository.zip") as archive:
                self.assertEqual(archive.namelist(), ["plugins/0.1.9/purifier.cjs"])
                self.assertEqual(archive.read("plugins/0.1.9/purifier.cjs"), (destination / "purifier.cjs").read_bytes())

    def test_released_source_missing_its_declared_runtime_cannot_fall_back(self):
        if shutil.which("node") is None:
            self.fail("Node is required to execute the published Yarn plugin")
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            root = work / "source"
            self.source(root, "pkgs/plugin")
            native = work / "published.cjs"
            native.write_text(packages.yarn_plugin(root, self.repository, self.revision))
            shutil.rmtree(root / "pkgs")
            tools = work / "bin"
            tools.mkdir()
            nix = tools / "nix"
            nix.write_text("#!" + sys.executable + "\nimport json,sys\nassert sys.argv[1:3]==['flake','metadata']\nprint(json.dumps({'path':" + repr(str(root)) + "}))\n")
            nix.chmod(0o755)
            result = subprocess.run(["node", str(native)], env=dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"]), text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runtime", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
