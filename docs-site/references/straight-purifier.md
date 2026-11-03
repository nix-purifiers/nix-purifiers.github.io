# straight-purifier

Locked, Nix-resolved packages for Emacs configurations using Straight.

## Quickstart

From your existing Emacs configuration directory:

```sh
nix shell 'github:nix-purifiers/straight-purifier'
straight-purifier --project . lock
straight-purifier --project . prefetch
emacs --init-directory "$PWD"
```

Commit `straight/versions/default.el` and `straight-purifier.lock.json`.
Your configuration still uses `straight-use-package`. The wrapper activates
Nix-built packages before loading your init file. Existing native checkouts
remain available for ordinary Emacs outside the wrapper.

Without a lockfile, the wrapper warns and runs ordinary, impure Emacs.
A damaged or stale lock fails with a repair command. You can install the
wrapper through your normal Nix configuration.

A native integration is also available. Install it through Straight:

```elisp
(straight-use-package
 '(straight-purifier
   :type git :host github
   :repo "nix-purifiers/straight-purifier"
   :files ("lisp/*.el")))
(require 'straight-purifier)
(straight-purifier-activate)
```

Place activation before your other package declarations. This integration
warns that its own resolution was impure; the wrapper resolves the
integration through Nix and activates it before user initialization.

## Development loop

After changing your configuration:

```sh
straight-purifier --project . lock
straight-purifier --project . prefetch
emacs --init-directory "$PWD"
```

`lock` keeps existing native commits, including when upstream branches
move. Repeating it without changes preserves lockfile bytes. Update all
packages and recipe repositories with:

```sh
straight-purifier --project . update
straight-purifier --project . prefetch
```

Or update one package:

```sh
straight-purifier --project . update s
```

Straight performs native resolution, dependency discovery, freezing and
updates in a private profile. The companion records Git URLs, NAR hashes,
commit metadata, normalized recipes and configuration fingerprints.
Native commit coordinates remain in `straight/versions/default.el`.

## Working offline

Run `prefetch` while inputs are available, then use Emacs normally.
It roots the complete package environment and Emacs toolchain beside the
selected lock. Packages are built with native Straight during the Nix
build. Runtime Straight activation uses its safe mode and rejects cloning,
fetching and native lock mutations.

All local `.el` configuration files are fingerprinted. Generated Straight
checkouts and caches are excluded. Keep configuration imports within the
configuration directory so they participate in the lock.

## Editor

The same environment supplies package autoloads, bytecode and source.
Normal `find-function`, help and completion use those packages. The sandbox
editor test follows a real function definition into its Nix store source.

## Troubleshooting

- **Configuration or native lock changed:** run `lock`, then `prefetch`.
- **Package updates are blocked in Emacs:** use `straight-purifier update`.
- **Emacs version differs:** use the intended Emacs through a scope override
  and update the lock with that toolchain.
- **An early init disables site loading:** omit `--no-site-file` for normal
  locked startup. Batch and quick modes receive explicit activation.
- **A custom build needs another compiler:** supply that toolchain through
  the Nix environment builder rather than downloading it during the build.

The default configuration is `init.el`, or `packages.el` for standalone
package declarations. `--config` selects another file. Multiple Straight
profiles, local-only recipes, and non-Git version-control backends are not
supported yet. Custom package build commands must work in the Nix sandbox.

External native and companion locks are supported:

```sh
straight-purifier --project . \
  --native-lock ../locks/versions.el \
  --lockfile ../locks/straight.json lock
straight-purifier --project . \
  --native-lock ../locks/versions.el \
  --lockfile ../locks/straight.json prefetch
```

Set `STRAIGHT_PURIFIER_NATIVE_LOCKFILE` and `STRAIGHT_PURIFIER_LOCKFILE`
for wrapper invocations using those external locks.

## Supported language repositories

Straight Git recipes and their Git-backed recipe repositories are locked
at native commits. Repository submodules and commit identity are retained.
Private transport requires appropriate fetcher overrides; credentials do
not belong in lockfiles. The CLI uses your native Git transport.

Git is the native plugin publication mechanism. GitHub Pages hosts the
documentation. The flake targets x86_64 and ARM Linux.

## Examples

[examples/config](examples/config) is a complete configuration using
`s.el`, with its native versions file and companion lock.

## Nix builds

For an optional sandbox check or configuration release, add this flake to
your project inputs and call its scoped builder:

```nix
pkgs.straight-purifier.buildStraightProject {
  src = ./.;
  testFile = ./tests.el;
}
```

Apply `inputs.straight-purifier.overlays.default` to your package set.
The result exposes `packages.environment`, `tests`, `release` and `fetches`.
`testFile` contains ERT tests. Without one, the builder activates every
locked recipe. `release` contains a deterministic configuration archive.
The builder also accepts external `lockFile`, `nativeLock`, `configFile`,
`fetchers`, `nativeBuildInputs` and `srcFilter` arguments.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
