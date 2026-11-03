# typst-purifier

Locked, Nix-resolved packages for Typst.

## Quickstart

```sh
nix shell 'github:nix-purifiers/typst-purifier'
typst-purifier lock
typst compile main.typ
```

The shell supplies Typst and Tinymist wrappers. Typst's native compiler selects
the packages; Nix supplies their readonly source and bundled WASM plugins.
Your document and output files remain in the working tree.

Without a companion lockfile, each wrapper warns and runs its ordinary, impure
tool. A stale or invalid lock fails. Commit `typst-purifier.lock.json` and
refresh package selection with:

```sh
typst-purifier lock --update
```

Use `--document path.typ` for another entry document. Document edits do not
require relocking unless they introduce a package absent from the lock.
`prefetch` prepares the package environment. The wrappers can also be installed
using your normal Nix configuration.

## Native tooling

```sh
typst watch main.typ
typst eval --in main.typ 'query(heading).len()'
tinymist lsp
```

Tinymist uses the same Nix package paths for diagnostics and source navigation.
Its locked registry prevents package downloads and index refreshes. For an
editor launched from outside the Nix shell:

```sh
typst-purifier exec -- your-editor .
```

The editor must invoke the supplied `tinymist` wrapper. Compiler rendering uses
the pinned embedded fonts. Custom external fonts and editor font overrides are
outside the current scope.

## What is locked

Native compilation records the transitive package set and retains the exact
archives it downloads. Their extracted files must match the native package
cache. The lock records archive URLs and hashes, package names, versions and
entrypoints, tracked configuration and SDK identity. Prepared packages verify
their metadata again. Missing packages fail before network access.

This version supports Typst 0.15.1, Tinymist 0.15.10 and versioned packages from
the `preview` registry. Local package workspaces and alternate registries are
outside its current scope. Changes to `typst.toml` or the SDK require relocking.
Use `lock --input path` to track other configuration files and
`lock --define key=value` to select native `sys.inputs` values.

## Artifacts and publication

```sh
typst-purifier bundle
typst-purifier publish --tag v0.1.0
```

`bundle` produces a reproducible PDF. For a project with package metadata in
`typst.toml`, it also produces a source package tarball that an ordinary Typst
installation can import from a local package directory. `publish` uploads these
exact files to an existing GitHub release; it does not submit to Typst Universe.

Use `--project` and `--lock` for an external companion. Native commands accept
`TYPST_PURIFIER_PROJECT` and `TYPST_PURIFIER_LOCK`. Environment profiles retain
the package environment and wrapper SDK as Nix garbage collector roots.

## Building with Nix

An optional project definition can use the overlay's named builder:

```nix
pkgs.typst-purifier.buildTypstProject {
  src = ./.;
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`packages.environment` contains the native packages; `packages.project`
contains the PDF and compiler dependency report. Override `typstFlags`,
`nativeBuildInputs` or `checkCommand` for project requirements.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
