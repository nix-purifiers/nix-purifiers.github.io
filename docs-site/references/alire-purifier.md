# alire-purifier

Locked, Nix-built Ada dependencies for Alire.

## Quickstart

```sh
nix shell 'github:nix-purifiers/alire-purifier'
alire-purifier lock
alr build
alr run
```

Alire's native resolver selects the dependencies from `alire.toml`. Nix fetches
those revisions, generates their native configurations, builds them and installs
their GPR projects. Your project builds in its working tree.

Commit `alire-purifier.lock.json`. Source edits do not require relocking. Change
the native manifest and update the lock to select other dependencies:

```sh
alire-purifier lock --update
```

The shell provides Alire, GNAT and GPR tools. Wrappers without a lockfile warn and
run the ordinary, impure tools. Invalid or stale locks fail. The integration can
also be installed through your normal Nix configuration.

## Development

Alire sees the compiled dependencies as native external packages. Their versions
and dependency constraints remain in its solution, and their GPR projects point
at readonly Nix sources and libraries. Private Alire settings and native project
metadata keep the working-tree build mutable.

```sh
alr clean
alr printenv
alire-purifier exec -- your-editor
```

GNAT and GPR-based editors use the same native project environment. Root project
commands retain their ordinary network access.

```sh
alire-purifier prefetch
```

`--input path` tracks additional selection files. Use `--project` and `--lock` for
an external companion; native wrappers accept `ALIRE_PURIFIER_PROJECT` and
`ALIRE_PURIFIER_LOCK`. Environment generations retain their dependency and SDK
closures for garbage collection.

The initial integration targets Linux with Alire 2.1.1, GNAT 16.2 and GPRbuild 25.
It supports exact Git source origins. Architecture-dependent dependency selection
and external system packages need additional integration. The SDK supplies the
compiler and build tools. Dependency selection and index changes go through lock
updates; ordinary build, run and inspection commands use the prepared solution.

## Publication

```sh
alire-purifier bundle
alire-purifier publish --tag v0.1.0
```

The reproducible source archive contains native Alire and GPR metadata. Ordinary
Alire can consume it. Publication uploads the exact realized bytes to an existing
GitHub release.

## Building with Nix

An optional definition can use the overlay's named builder:

```nix
pkgs.alire-purifier.buildAlireProject {
  src = ./.;
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`libraryOverrides` supplies crate-specific build changes.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
