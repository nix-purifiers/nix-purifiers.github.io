"""Build the native integrations using the repository's locked Nix toolchain."""
import atexit
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from urllib.parse import quote


def _locked_source(reference, roots):
    metadata = json.loads(subprocess.check_output([
        "nix", "flake", "metadata", "--json", "--no-update-lock-file", reference
    ], text=True))
    nar_hash = metadata["locked"]["narHash"]
    # Metadata may describe a lazy tree whose store path does not exist yet.
    archive = json.loads(subprocess.check_output([
        "nix", "flake", "archive", "--json", "--no-update-lock-file", reference
    ], text=True))
    source = Path(archive["path"])
    actual_hash = subprocess.check_output([
        "nix", "hash", "path", "--type", "sha256", "--sri", str(source)
    ], text=True).strip()
    if actual_hash != nar_hash:
        raise RuntimeError("Flake source changed while materializing the release snapshot")
    subprocess.check_output([
        "nix-store", "--add-root", str(roots / "source"), "--indirect", "--realise", str(source)
    ], text=True)
    return "path:" + str(source) + "?narHash=" + quote(nar_hash, safe="")


def nix_build(attribute, *, version=None):
    temporary = tempfile.TemporaryDirectory(prefix="purifier-release-build-")
    roots = Path(temporary.name).resolve()
    try:
        arguments = ["nix", "build", "--out-link", str(roots / "result"),
                     "--print-out-paths", "--no-update-lock-file"]
        if version is None:
            arguments.append(attribute)
        else:
            source = _locked_source(".", roots)
            system = json.loads(subprocess.check_output(["nix", "config", "show", "--json"], text=True))["system"]["value"]
            name, _, output = attribute.removeprefix(".#").partition("^")
            if name not in ("plugin", "extension") or output not in ("", "dist"):
                raise ValueError("Unsupported versioned release package")
            expression = (
                "let source = builtins.getFlake " + json.dumps(source) + "; "
                "package = source.packages." + json.dumps(system) + "." + name
                + ".override { version = " + json.dumps(version) + "; }; in package"
                + ("." + output if output else "")
            )
            arguments.extend(["--expr", expression])
        result = Path(subprocess.check_output(arguments, text=True).strip())
    except BaseException:
        temporary.cleanup()
        raise
    # Keep both the snapshot and build outputs alive while callers copy assets.
    # Only links in this owned temporary directory are removed on process exit.
    atexit.register(temporary.cleanup)
    return result


def ant_plugin(source, repository, sha):
    """Let native Ant activate the runtime from this exact released commit."""
    target = io.BytesIO()
    resource = "org/nixpurifiers/ant/release.properties"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output:
        for entry in original.infolist():
            if entry.filename != resource:
                output.writestr(entry, original.read(entry.filename))
        entry = zipfile.ZipInfo(resource, (1980, 1, 1, 0, 0, 0))
        output.writestr(entry, f"reference=github:{repository}/{sha}\n")
    return target.getvalue()


def poetry_bootstrap(repository, sha):
    """Only published wheels need to discover the Nix-provided runtime."""
    reference = f"github:{repository}/{sha}#poetry"
    return f'''# Generated for the published plugin; the Nix wrapper supplies these paths directly.
import json
import os
import subprocess
import sys

def configure():
    if os.environ.get("POETRY_PURIFIER_REALIZE") or os.environ.get("POETRY_PURIFIER_MODE") or os.environ.get("POETRY_PURIFIER") == "0":
        return
    print("poetry-purifier: warning: the plugin was resolved impurely; use the Nix wrapper for pure plugin resolution.", file=sys.stderr)
    reference = {reference!r}
    wrapper = subprocess.check_output(["nix", "build", "--no-link", "--print-out-paths", reference], text=True).strip()
    runtime = json.loads(subprocess.check_output(["nix", "eval", "--json", reference + ".purifierRuntime"], text=True))
    os.environ["POETRY_PURIFIER_REALIZE"] = runtime["realize"]
    os.environ["POETRY_PURIFIER_BUILD"] = runtime["build"]
    os.environ["POETRY_PURIFIER_POETRY"] = wrapper
    os.environ["PATH"] = wrapper + "/bin:" + runtime["path"] + ":" + os.environ.get("PATH", "")
'''


def yarn_plugin(root, repository, sha):
    source = (root / "plugin/purifier.cjs").read_text()
    foreign = (root / "plugin/foreign.cjs").read_text()
    source = source.replace('const foreign = require("./foreign.cjs");',
        'const foreign = (() => { const module = {exports: {}};\n' + foreign + '\nreturn module.exports; })();')
    reference = f"github:{repository}/{sha}"
    bootstrap = f'''console.error("yarn-berry-purifier: warning: the plugin was resolved impurely; use the Nix wrapper for pure plugin resolution.");
const releaseRef = {json.dumps(reference)};
const releaseSource = JSON.parse(childProcess.execFileSync("nix", ["flake", "metadata", "--json", releaseRef], {{encoding: "utf8"}})).path;
const releaseNixpkgs = childProcess.execFileSync("nix", ["eval", "--raw", "--impure", "--expr", `(builtins.getFlake "${{releaseRef}}").inputs.nixpkgs.outPath`], {{encoding: "utf8"}}).trim();
'''
    source = source.replace('const NIX_LIB = "@nixLib@";', bootstrap + 'const NIX_LIB = path.join(releaseSource, "nix/lib");')
    source = source.replace('const NIXPKGS = "@nixpkgs@";', 'const NIXPKGS = releaseNixpkgs;')
    source = source.replace('const FLAKE = "@flake@";', 'const FLAKE = releaseSource;')
    assert all(token not in source for token in ('@nixLib@', '@nixpkgs@', '@flake@'))
    return source


def build(root, repository, sha, version, kind, destination):
    native = destination / "native"
    native.mkdir()
    name = repository.split("/")[1]
    if kind == "python":
        if name == "poetry-purifier":
            generated = root / "src/poetry_purifier/_release.py"
            generated.write_text(poetry_bootstrap(repository, sha))
            subprocess.run(["git", "add", "--intent-to-add", str(generated)], check=True)
        dist = nix_build(".#plugin^dist", version=version)
        project = native / "simple" / name
        project.mkdir(parents=True)
        wheels = list(dist.glob("*.whl"))
        if not wheels:
            raise RuntimeError("The plugin build produced no wheel")
        for wheel in wheels:
            shutil.copyfile(wheel, project / wheel.name)
            # Also provide direct, versioned release downloads.
            shutil.copyfile(wheel, destination / wheel.name)
    elif kind in ("maven", "ant"):
        if kind == "maven":
            extension = nix_build(".#extension", version=version)
            artifact = "maven-purifier-extension"
            title = "Maven purifier recording extension"
        else:
            extension = nix_build(".#plugin")
            artifact = "ant-purifier"
            title = "Ant purifier integration"
        project = native / "maven/io/github/nix-purifiers" / artifact / version
        project.mkdir(parents=True)
        jar = project / f"{artifact}-{version}.jar"
        source = extension / "share/java" / f"{artifact}.jar"
        if kind == "ant":
            jar.write_bytes(ant_plugin(source, repository, sha))
        else:
            shutil.copyfile(source, jar)
        jar.with_suffix(".pom").write_text(
            '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
            f'<groupId>io.github.nix-purifiers</groupId><artifactId>{artifact}</artifactId>'
            f'<version>{version}</version><name>{title}</name></project>\n')
        for file in list(project.iterdir()):
            for algorithm in ("sha1", "sha256", "sha512"):
                file.with_suffix(file.suffix + "." + algorithm).write_text(
                    hashlib.new(algorithm, file.read_bytes()).hexdigest() + "\n")
    elif kind == "yarn":
        project = native / "plugins" / version
        project.mkdir(parents=True)
        plugin = project / "purifier.cjs"
        plugin.write_text(yarn_plugin(root, repository, sha))
        subprocess.run(["node", "--check", str(plugin)], check=True)
        shutil.copyfile(plugin, destination / "purifier.cjs")
    elif kind != "source":
        raise ValueError(f"Unknown native package kind: {kind}")
    if kind != "source":
        with zipfile.ZipFile(destination / "native-repository.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(native.rglob("*")):
                if file.is_file():
                    info = zipfile.ZipInfo(str(file.relative_to(native)), (1980, 1, 1, 0, 0, 0))
                    archive.writestr(info, file.read_bytes())
    shutil.rmtree(native)
