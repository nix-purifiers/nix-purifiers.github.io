# agda-purifier

Locked, Nix-resolved libraries for Agda.

## Quickstart

```sh
nix shell 'github:nix-purifiers/agda-purifier'
agda-purifier lock
agda Main.agda
```

Agda selects dependencies from your project's `.agda-lib` files and its existing
`libraries` registry. Capture requires registered dependencies to be clean Git
checkouts with an `origin` remote. Nix fetches those exact revisions and builds
their interfaces; your project stays in its working tree.

Use `--libraries path` to select a registry explicitly. Commit
`agda-purifier.lock.json`. Source edits do not require relocking. To change library
selection, update the native metadata and lock:

```sh
agda-purifier lock --update
agda --build-library
```

The shell provides the `agda` wrapper. It can also be installed through your
normal Nix configuration. Without a lockfile, it warns and runs ordinary, impure
Agda. Invalid and stale locks fail.

## Development and editors

Agda keeps the project's mutable interfaces under its normal `_build/` directory.
Dependency sources and interfaces remain readonly in Nix. The wrapper uses a
private configuration under `.agda-purifier/`, keeping ambient user libraries,
defaults and trusted executables out of locked resolution.

Editors that invoke `agda --interaction` or `agda --interaction-json` through
`PATH` use the same environment. Native highlighting and definition locations
point into dependency sources in Nix.

```sh
agda-purifier prefetch
agda-purifier exec -- your-command
```

`--input path` tracks additional selection files. Use `--project` and `--lock`
for an external companion; native commands accept `AGDA_PURIFIER_PROJECT` and
`AGDA_PURIFIER_LOCK`. Environment generations retain their compiler, libraries
and frontend SDK for garbage collection while older sessions remain active.

The initial integration targets Agda 2.8.0 on Linux. Dependency Git trees must
contain their source include directories. Dependencies on the mutable current
directory and custom library-registry flags are unsupported in locked commands.
`--ignore-interfaces` cannot rewrite readonly dependency interfaces.

## Publication

```sh
agda-purifier bundle
agda-purifier publish --tag v0.1.0
```

The reproducible source archive contains native Agda metadata. Ordinary Agda can
consume it with a native library registry. Publication uploads the exact realized
archive to an existing GitHub release.

## Building with Nix

An optional definition can use the overlay's named builder:

```nix
pkgs.agda-purifier.buildAgdaProject {
  src = ./.;
  doCheck = true;
  checkCommand = "agda Proof.agda";
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`libraryOverrides` supplies library-specific build changes.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
