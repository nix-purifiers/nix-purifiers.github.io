"""Release a checked main commit, with automatic versions and immutable assets."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import packages


def run(*arguments, **kwargs):
    return subprocess.check_output(arguments, text=True, **kwargs).strip()


def api(repository, suffix):
    return json.loads(run("gh", "api", f"repos/{repository}/{suffix}"))


def fingerprint(root, revision):
    tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", revision], cwd=root)
    entries = []
    for item in tree.split(b"\0"):
        if not item:
            continue
        name = item.split(b"\t", 1)[1].decode()
        if name.startswith(("tests/", "docs/", ".github/")) or name in ("README.md", ".gitignore"):
            continue
        entries.append(item)
    return hashlib.sha256(b"\0".join(entries)).hexdigest()


def next_version(series, tags):
    if not re.fullmatch(r"\d+\.\d+", series):
        raise ValueError("Release series must have the form MAJOR.MINOR")
    revisions = [int(tag[len(series) + 2:]) for tag in tags
                 if re.fullmatch(r"v" + re.escape(series) + r"\.\d+", tag)]
    return series + "." + str(max(revisions, default=0) + 1)


def checked(repository, sha):
    runs = api(repository, f"actions/workflows/check.yml/runs?branch=main&head_sha={sha}&status=success&per_page=100")
    return any(r["head_sha"] == sha and r["head_branch"] == "main"
               and r["event"] in ("push", "workflow_dispatch") for r in runs["workflow_runs"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--kind", choices=("source", "python", "maven", "ant", "yarn"), default="source")
    parser.add_argument("--series", default="0.1")
    args = parser.parse_args()
    root = Path.cwd()
    sha = run("git", "rev-parse", "HEAD")
    if sha != args.sha:
        raise RuntimeError("The checkout does not match the requested release commit")
    if api(args.repository, "git/ref/heads/main")["object"]["sha"] != sha:
        print("A newer main commit exists; its successful CI will release it.")
        return
    if not checked(args.repository, sha):
        raise RuntimeError("This main commit has no successful check workflow; refusing to tag it")
    identity = fingerprint(root, sha)
    releases = api(args.repository, "releases?per_page=100")
    for release in releases:
        if release["draft"] or release["prerelease"]:
            continue
        assets = {a["name"] for a in release["assets"]}
        if "release-manifest.json" not in assets:
            continue
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run(["gh", "release", "download", release["tag_name"], "--repo", args.repository,
                            "--pattern", "release-manifest.json", "--dir", temporary], check=True)
            previous = json.loads(Path(temporary, "release-manifest.json").read_text())
        if previous["series"] == args.series and previous["fingerprint"] == identity and previous["kind"] == args.kind:
            print("The latest release already contains these sources and locked dependencies.")
            if args.kind != "source":
                subprocess.run(["gh", "workflow", "run", "pages.yml", "--repo", args.repository, "--ref", "main"], check=True)
            return
        break
    version = next_version(args.series, run("git", "tag", "--list").splitlines())
    with tempfile.TemporaryDirectory() as temporary:
        destination = Path(temporary)
        packages.build(root, args.repository, sha, version, args.kind, destination)
        manifest = {"version": version, "series": args.series, "commit": sha,
                    "fingerprint": identity, "kind": args.kind}
        (destination / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        archive = subprocess.check_output(["git", "archive", "--format=tar", "--prefix=" + args.repository.split("/")[1] + "/", sha])
        (destination / "source.tar.gz").write_bytes(gzip.compress(archive, mtime=0))
        sums = "".join(hashlib.sha256(f.read_bytes()).hexdigest() + "  " + f.name + "\n"
                       for f in sorted(destination.iterdir()))
        (destination / "SHA256SUMS").write_text(sums)
        if api(args.repository, "git/ref/heads/main")["object"]["sha"] != sha:
            print("Main advanced during the build; leaving publication to the newer commit.")
            return
        notes = destination / "notes.md"
        notes.write_text(f"Checked sources and locked Nix dependencies from `{sha}`.\n\n"
                         "Assets include the source archive, release manifest and SHA-256 checksums.\n"
                         + ("The native package repository is rebuilt on GitHub Pages from the attached archive.\n" if args.kind != "source" else ""))
        assets = [str(p) for p in destination.iterdir() if p != notes]
        subprocess.run(["gh", "release", "create", "v" + version, "--repo", args.repository,
                        "--target", sha, "--title", "v" + version, "--notes-file", str(notes), *assets], check=True)
    if args.kind != "source":
        # GITHUB_TOKEN release events do not start workflows; dispatch explicitly.
        subprocess.run(["gh", "workflow", "run", "pages.yml", "--repo", args.repository, "--ref", "main"], check=True)


if __name__ == "__main__":
    main()
