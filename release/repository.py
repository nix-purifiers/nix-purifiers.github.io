"""Rebuild native package repositories from immutable GitHub release assets."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile


def version_key(value):
    return tuple(int(x) for x in value.removeprefix("v").split("."))


def extract(archive, destination):
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("Archive member escapes the package repository")
        z.extractall(destination)


def indexes(site):
    simple = site / "simple"
    if simple.exists():
        names = []
        for project in sorted(simple.iterdir()):
            if not project.is_dir():
                continue
            names.append(project.name)
            links = []
            for wheel in sorted(project.glob("*.whl")):
                digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
                name = html.escape(wheel.name, quote=True)
                links.append(f'<a href="{name}#sha256={digest}">{name}</a><br>')
            (project / "index.html").write_text("<!doctype html>\n" + "\n".join(links))
        simple.joinpath("index.html").write_text("<!doctype html>\n" + "\n".join(
            f'<a href="{name}/">{name}</a><br>' for name in names))
    plugins = site / "plugins"
    if plugins.exists():
        versions = [p for p in plugins.iterdir() if p.is_dir() and re.fullmatch(r"\d+\.\d+\.\d+", p.name)]
        if versions:
            newest = max(versions, key=lambda p: version_key(p.name))
            (plugins / "purifier.cjs").write_bytes((newest / "purifier.cjs").read_bytes())
    maven = site / "maven"
    if maven.exists():
        for artifact in maven.glob("io/github/nix-purifiers/*"):
            versions = sorted([p.name for p in artifact.iterdir() if p.is_dir()], key=version_key)
            if not versions:
                continue
            xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<metadata>"
                   "<groupId>io.github.nix-purifiers</groupId>"
                   f"<artifactId>{artifact.name}</artifactId><versioning>"
                   f"<latest>{versions[-1]}</latest><release>{versions[-1]}</release><versions>"
                   + "".join(f"<version>{v}</version>" for v in versions)
                   + "</versions></versioning></metadata>\n")
            metadata = artifact / "maven-metadata.xml"
            metadata.write_text(xml)
            for algorithm in ("sha1", "sha256", "sha512"):
                metadata.with_suffix(metadata.suffix + "." + algorithm).write_text(
                    hashlib.new(algorithm, metadata.read_bytes()).hexdigest() + "\n")


def download(repository, site):
    releases = json.loads(subprocess.check_output([
        "gh", "api", "--paginate", "--slurp", f"repos/{repository}/releases?per_page=100"
    ], text=True))
    with tempfile.TemporaryDirectory() as temporary:
        for page in releases:
            for release in page:
                if release["draft"] or release["prerelease"]:
                    continue
                for asset in release["assets"]:
                    if asset["name"] != "native-repository.zip":
                        continue
                    archive = Path(temporary) / (str(asset["id"]) + ".zip")
                    subprocess.run(["gh", "release", "download", release["tag_name"],
                                    "--repo", repository, "--pattern", "native-repository.zip",
                                    "--output", str(archive)], check=True)
                    extract(archive, site)
    indexes(site)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--site", required=True, type=Path)
    args = parser.parse_args()
    download(args.repository, args.site)
