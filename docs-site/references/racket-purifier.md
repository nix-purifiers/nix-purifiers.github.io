# racket-purifier

Locked, Nix-resolved dependencies for Racket.

## Quickstart

In a package with `info.rkt`:

```sh
nix shell 'github:nix-purifiers/racket-purifier'
racket-purifier lock
raco pkg install .
raco make main.rkt
raco test main.rkt
```

The `racket` and `raco` wrappers activate the locked dependencies and a private
user package scope. Dependency sources and bytecode stay in the Nix store;
your package remains linked to its working tree. Existing user packages and
configuration do not affect the session. Private state lives under
`compiled/racket-purifier/`.

The wrappers are required. Install them using your preferred configuration or
package manager if you want them beyond `nix shell`. Without a purifier
lockfile they warn and run ordinary, impure Racket commands.

## Locks and updates

Commit `racket-purifier.lock.json`.

```sh
racket-purifier lock --update
racket-purifier prefetch
```

Racket's native package manager selects dependencies, including build and test
packages. The purifier captures native catalog identities, checksums and exact
archive/Git sources. Nix installs them without further resolution and prepares
their bytecode. Native child processes inherit the same package configuration.

The SDK is minimal Racket CS. Declare tools such as `compiler-lib` and
`rackunit-lib` in `build-deps` when your package needs them.

An unchanged lock is retained. Changes to `info.rkt` or the SDK require an
update. Track additional metadata files with `lock --input path`; choose a
stable package name with `lock --name my-package`.

This adapter supports HTTPS package archives and pinned Git sources. Git package
subtrees are checked against the source installed by Racket. Unsupported source
kinds fail during capture. Native libraries must be supplied explicitly to the
Nix builder.

For an external lock:

```sh
racket-purifier --project "$PWD" \
  --lock-file /path/to/package.lock.json lock
export RACKET_PURIFIER_PROJECT="$PWD"
export RACKET_PURIFIER_LOCK=/path/to/package.lock.json
raco test main.rkt
```

## Nix builds and publication

The overlay provides `racket-purifier.buildRacketProject`. Pass `src`, and
optionally `lockFile`, `nativeBuildInputs`, `buildCommand`, `checkCommand`, or
`installCommand`. It provides `packages.environment`, `packages.project`,
`tests`, `release`, and `fetches`.

The project output contains source, compiled bytecode, and `racket`/`raco`
launchers configured for the installed package. The default check uses
`raco test -p`.

`racket-purifier release` uses native `pkg-create` to produce a source ZIP and
its `.CHECKSUM` sidecar. `publish --repo OWNER/REPO --tag TAG` uploads those
same files. Ordinary `raco pkg install` can consume the ZIP.

The wrapper itself is distributed through the flake and GitHub source releases;
no additional Racket plugin is required.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
