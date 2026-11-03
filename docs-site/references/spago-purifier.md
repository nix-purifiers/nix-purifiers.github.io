# spago-purifier

Locked, Nix-resolved dependencies for PureScript's native Spago workflow.

## Quickstart

From a project with `spago.yaml`:

```sh
nix shell 'github:nix-purifiers/spago-purifier'
spago-purifier lock
spago-purifier prefetch
spago build
spago test
spago run
```

The shell provides Spago, PureScript, Node.js and esbuild. A wrapper is required
to activate the locked dependency modules. Without a companion lockfile, it
warns and runs ordinary, impure Spago. Install it with your usual installation
method if you want it available beyond the shell.

Commit `spago.lock` and `spago-purifier.lock.json`. Native Spago selects the
versions. The companion records registry commits, archive integrity hashes and
workspace manifests. Locking fetches sources; dependency compilation happens
inside Nix. Application edits compile in your working tree and reuse those
immutable modules.

## Updates and sessions

```sh
spago-purifier lock --update
spago-purifier prefetch
```

Updates use native Spago's upgrade command. Normal relocking reuses the captured
registry commits. Manifest or native lock changes require locking again.

Compiled application modules and native registry caches live in a private
`.spago-purifier/` session. Ordinary `.spago/p` packages cannot override the Nix
sources. Ignore `.spago/`, `.spago-purifier/` and `output/` in Git.

```sh
spago-purifier shell
```

The project shell propagates the locked environment to child commands. The
wrapper retains the environment and SDK with project GC roots.

## Editors

The supplied `purs` wrapper configures PureScript's native IDE server with the
session output and Nix dependency sources. Editors using `purs ide server` can
resolve dependency definitions into the Nix store.

## Build the project in Nix

Optionally use the overlay's builder:

```nix
pkgs.spago-purifier.buildSpagoProject {
  src = ./.;
}
```

It returns `packages.environment`, `packages.project`, `packages.default`,
`tests`, `release` and `fetches`. Output names are known during evaluation.
`fetchers`, `nativeBuildInputs`, `doCheck`, `buildCommand`, `checkCommand` and
`srcFilter` customize the build. The default runs native build and test commands.
`release` contains a source tarball with both lockfiles.

```sh
spago-purifier publish \
  --repo OWNER/REPO \
  --tag vVERSION
```

## Current scope

Spago 1.0.5 and PureScript 0.15.16 on Linux x86_64 and aarch64. Registry packages,
package sets and solver workspaces are supported. Git and external path package
providers need additional capture adapters. Workspace YAML files must be within
the project. JavaScript FFI dependencies from npm need a separate npm integration.

Locked commands use offline resolution and private output directories. Changing
package selections, registry refreshes or output directories through native
commands is refused; use the helper to update the lock.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
