# zef-purifier

Locked, Nix-resolved dependencies for Raku and zef.

## Quickstart

In a project with `META6.json`:

```sh
nix shell 'github:nix-purifiers/zef-purifier'
zef-purifier lock
zef install .
raku -Ilib t/basic.rakutest
```

The `zef` and `raku` wrappers activate the project's locked repository.
Dependencies and their precompiled modules live in the Nix store; application
code and its compilation cache remain writable. Each project gets private zef
configuration and caches in `.zef-purifier/`.

The wrappers are required for activation. Install them using your preferred
configuration or package manager if you want them available beyond `nix shell`.
Without a lockfile they warn and run the ordinary, impure tool.

## Locking and updates

`lock` uses zef's native resolver to capture exact distribution identities,
metadata, and hashed source archives, including build and test dependencies.
It stops before dependency builds, tests, or installation. Nix installs those
archives without further resolution and prepares their bytecode.

```sh
zef-purifier lock --update
zef-purifier prefetch
zef test .
```

An unchanged lock is retained by `lock`; `--update` resolves afresh. Changes to
`META6.json` or the pinned SDK require an update. Locked sessions reject
commands that change dependency resolution.

The initial adapter supports HTTPS distribution archives. Git and local path
dependencies fail during capture rather than falling back to impure resolution.
Native libraries needed by modules must be provided explicitly to the Nix
builder; they are not inferred from the host.

For an external lockfile:

```sh
zef-purifier --project "$PWD" \
  --lock-file /path/to/project.lock.json lock
export ZEF_PURIFIER_PROJECT="$PWD"
export ZEF_PURIFIER_LOCK=/path/to/project.lock.json
raku -Ilib t/basic.rakutest
```

## Nix builds

The overlay provides `zef-purifier.buildZefProject`. Its result contains
`packages.environment`, `packages.project`, `tests`, `release`, and `fetches`.
Pass `src`, and optionally `lockFile`, `nativeBuildInputs`, `buildCommand`,
`checkCommand`, and `installCommand`. The default build runs `zef build .` when a build hook exists, tests
`t/*.rakutest`, and installs `lib` and `META6.json`.

`zef-purifier release` produces a deterministic source archive with the lockfile.
The wrapper itself is distributed through the Nix flake and GitHub source
releases; no additional ecosystem plugin is needed.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
