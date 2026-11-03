# buf-purifier

Locked, Nix-resolved Protobuf modules for Buf.

## Quickstart

```sh
nix shell 'github:nix-purifiers/buf-purifier'
buf-purifier lock
buf build
buf lint
buf generate
```

Buf's native resolver writes `buf.lock`. Nix supplies its digest-checked modules
through a private cache whose module sources are readonly. Your workspace remains
mutable, and source edits do not require relocking.

Commit `buf.lock` and `buf-purifier.lock.json`. After changing dependency selection:

```sh
buf-purifier lock --update
```

The wrapper warns and uses ordinary, impure Buf when there is no purifier lock.
Invalid or stale locks fail. Install the integration through your normal Nix
configuration if you want it available beyond the temporary shell.

## Development

```sh
buf format -w
buf-purifier exec -- your-editor
buf-purifier prefetch
```

Buf's language server uses the same locked modules. Dependency cache misses fail
before registry fetching; ordinary root commands retain their network access.
Private writable lock files and tool caches use `XDG_CACHE_HOME`.
The working tree's `.buf-purifier` retains the prepared SDK profile.

The initial integration supports v2 workspaces, public BSR modules with b5 digests, and
`protoc_builtin` generators supplied by the Nix Protobuf compiler. Remote and
external plugins need additional Nix tool providers. Generated output stays in
your normal working-tree directories.

`--input path` tracks extra selection files. Use `--project` and `--lock` for an
external companion; wrappers accept `BUF_PURIFIER_PROJECT` and
`BUF_PURIFIER_LOCK`. Prepared sessions retain their dependency and SDK closures
for garbage collection.

## Publication

```sh
buf-purifier bundle
buf-purifier publish --tag v0.1.0
```

The reproducible source archive contains native Buf configuration and schemas.
Ordinary Buf can consume it. Publication uploads the exact realized archive to
an existing GitHub release.

## Building with Nix

The overlay provides a named builder:

```nix
pkgs.buf-purifier.buildBufProject {
  src = ./.;
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`. The
project output includes the native descriptor image and generated sources.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
