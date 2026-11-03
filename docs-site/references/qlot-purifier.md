# qlot-purifier

Locked, Nix-resolved dependencies for Qlot and Common Lisp.

## Quickstart

In a project with `qlfile` and ASDF system definitions:

```sh
nix shell 'github:nix-purifiers/qlot-purifier'
qlot-purifier lock
qlot install
qlot exec sbcl
```

Then use the normal Lisp commands:

```lisp
(ql:quickload "my-system")
(asdf:test-system "my-system")
```

The `qlot` and `sbcl` wrappers activate a private project session. Dependency
sources and compiled FASLs live in the Nix store; application code and its FASLs
remain writable. An existing `.qlot` installation is left in place.

The wrappers are required for activation. Install them using your preferred
configuration or package manager if you want them beyond `nix shell`. Without a
purifier lockfile they warn and run the ordinary, impure tool.

## Locking and updates

Commit both `qlfile.lock` and `qlot-purifier.lock.json`.

```sh
qlot-purifier lock --update
qlot-purifier prefetch
qlot check
```

Qlot and ASDF select the dependency graph. The purifier captures exact release
archives and index metadata, then Nix installs and compiles that graph offline.
Resolution loads ASDF system definitions and may compile their definition
helpers in a temporary session; those compiled files are discarded.

`lock` retains an unchanged lock. `--update` uses Qlot's native update command.
Changes to `qlfile`, ASDF definitions, or the SDK require an update. Additional
files read by system definitions can be tracked with `lock --input path`.
Locked sessions reject commands that change dependency resolution.

This adapter currently supports HTTPS release archives, including ordinary
Quicklisp releases. Other Qlot source providers fail during capture. Native
libraries must be provided explicitly to the Nix builder.

For externally stored locks:

```sh
qlot-purifier --project "$PWD" \
  --lock-file /path/to/project.lock.json \
  --native-lock-file /path/to/qlfile.lock lock
export QLOT_PURIFIER_PROJECT="$PWD"
export QLOT_PURIFIER_LOCK=/path/to/project.lock.json
export QLOT_PURIFIER_SNAPSHOT=/path/to/qlfile.lock
qlot exec sbcl
```

## Nix builds

The overlay provides `qlot-purifier.buildQlotProject`. Pass `src` and optionally
`system`, `lockFile`, `snapshot`, `nativeBuildInputs`, `buildCommand`,
`checkCommand`, or `installCommand`. The default system is selected from the
project's top-level `.asd` files. The result provides `packages.environment`,
`packages.project`, `tests`, `release`, and `fetches`.

The project output contains `setup.lisp`, source, and compiled FASLs. Loading
that setup with ordinary SBCL activates the installed system and its
Nix-resolved dependencies.

`qlot-purifier release` creates a deterministic source archive with both locks.
`publish --repo OWNER/REPO --tag TAG` uploads that same archive to a GitHub
release. The wrapper itself is distributed through the flake and GitHub source
releases; no additional Lisp plugin is required.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
