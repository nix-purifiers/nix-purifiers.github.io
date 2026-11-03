# tectonic-purifier

Locked, Nix-resolved TeX support files for Tectonic.

## Quickstart

```sh
nix shell 'github:nix-purifiers/tectonic-purifier'
tectonic-purifier lock
tectonic -X build
```

For a standalone document:

```sh
tectonic-purifier lock main.tex
tectonic main.tex
```

Locking runs the native build to discover its support files. Nix supplies those
files and a prebuilt LaTeX format. Your TeX sources and build outputs stay in the
working tree.

Commit `tectonic-purifier.lock.json`. Text edits use the same lock. After adding
packages or changing the document's bundle, update it:

```sh
tectonic-purifier lock --update
```

The wrappers warn and use ordinary, impure Tectonic when there is no purifier
lock. Invalid or stale locks fail. Install the integration through your normal
Nix configuration if you want it beyond the temporary shell.

## Development

```sh
tectonic main.tex --synctex
tectonic-purifier exec -- your-editor
tectonic-purifier prefetch
```

Native PDF and SyncTeX output support the normal editor workflow. Private caches
and SDK profiles use `XDG_CACHE_HOME`. Support files and format data are readonly
Nix artifacts; missing support files require a lock update. User commands retain
their ordinary network access.

The initial integration supports LaTeX, Tectonic 0.17 and public indexed-tar
bundles. Fonts come from the locked bundle or explicit project font files;
ambient system font collections need additional integration.

`--input path` tracks additional selection files. Use `--project` and `--lock`
for an external companion; wrappers accept `TECTONIC_PURIFIER_PROJECT` and
`TECTONIC_PURIFIER_LOCK`. Prepared sessions retain their dependencies and SDK
closures for garbage collection.

## Publication

```sh
tectonic-purifier bundle
tectonic-purifier publish --tag v0.1.0
```

The reproducible archive contains the document's native source tree. Ordinary
Tectonic can consume it. Publication uploads the exact realized archive to an
existing GitHub release.

## Building with Nix

The overlay provides a named builder:

```nix
pkgs.tectonic-purifier.buildTectonicProject {
  src = ./.;
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
