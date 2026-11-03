# elpaca-purifier

Use Elpaca with Emacs packages resolved and locked by Nix.

From an existing Emacs configuration repository using Elpaca:

```sh
nix shell 'github:nix-purifiers/elpaca-purifier'
elpaca-purifier lock --project .
emacs --init-directory "$PWD"
```

Commit `elpaca-lock.el` and `elpaca-purifier.lock.json`. Locking uses Elpaca's
native recipe resolution, dependency queue, and lock export in a private cache.
Nix builds the selected packages with Elpaca's native build steps. A fresh
Emacs process verifies those packages before either lockfile is written.

This integration requires the Emacs wrapper. It supplies the pinned manager
before user initialization and activates readonly Nix-built packages through
Elpaca. Your existing Elpaca checkouts are preserved. Without a companion lock,
the wrapper warns and runs ordinary, impure Emacs. Install it using your usual
installation method if you want it available beyond `nix shell`.

Configuration settings remain editable. The integration checks the native
parsed recipes before activation; changing dependency selection requires
relocking. Native update, rebuild, and delete operations direct you to the
lock command:

```sh
elpaca-purifier lock --project . --update
elpaca-purifier prefetch --project .
```

Elpaca state, private aliases, writable caches, and Nix GC roots live beneath
`$XDG_CACHE_HOME/elpaca-purifier`. Editor commands retain normal networking.
Source and documentation navigation use the pinned package sources.

Without `--project`, the CLI uses the normal Emacs configuration directory.
The wrapper also honors `--init-directory`. `--config packages.el` can select a
separate, batch-compatible configuration for capture. It must select the same
packages as the editor profile. `--lock` and `--native-lock` accept external
lockfiles. Their environment equivalents are `ELPACA_PURIFIER_PROJECT`,
`ELPACA_PURIFIER_LOCK`, and `ELPACA_PURIFIER_NATIVE_LOCK`.

## Optional Nix build

The overlay exposes `buildElpacaProject` with `src`, `configFile`, `emacsArgs`,
`doCheck`, and `checkCommand`. It exposes `packages`, `tests`, `release`, and
`fetches`; output names are known without import-from-derivation.

`elpaca-purifier bundle` produces a native configuration source archive with
the manager, Git sources, and built packages vendored in Elpaca's normal layout.
`elpaca-purifier publish --tag TAG` uploads that exact archive to an existing
GitHub release.

## Scope

The initial implementation supports public HTTPS Git packages with standard
Elisp builds on Linux x86-64 and ARM64. Custom build steps, build variables,
shared repositories, submodules, and native modules need additional providers.
The configuration used for capture must work in batch mode. Conditional
profiles must select the same dependencies when locked and launched.

The SDK pins Emacs and Elpaca. Package history beyond the locked commit,
external language servers, and dependencies downloaded by package code are
outside this lock's scope. Bare `-Q` sessions bypass configuration normally.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
