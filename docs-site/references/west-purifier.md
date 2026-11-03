# west-purifier

Lock West's Git projects with Nix, then use native West commands in your working tree.

In an existing workspace initialized with `west init`:

```sh
nix shell 'github:nix-purifiers/west-purifier'
west-purifier lock
west build
```

Commit `west-purifier.lock.json` in the manifest repository alongside `west.yml`.
`lock` runs native West update and freeze in a temporary workspace, follows
imported manifests, and records exact Git revisions and verified Nix source
hashes. Your existing checkouts and local changes are preserved. Run
`west-purifier lock --update` after changing manifest selection.

This integration requires the wrapper. It supplies a private West workspace
with readonly Nix Git projects and a link to your editable manifest repository.
Native extensions obtain their dependency paths through West's manifest API;
hardcoded sibling paths outside that workspace need adaptation. The wrapper
also sets up a private Python virtualenv with the pinned West SDK available.

```sh
west list
west status
west manifest --freeze
west-purifier exec -- python -c \
  'from west.manifest import Manifest; print(Manifest.from_topdir().projects)'
```

Without a lockfile, the wrapper warns and runs ordinary, impure West. You can
install the wrapper using your usual installation method; the quickstart uses a
temporary `nix shell`. In a locked project use `lock --update` instead of
`west update` to change dependencies.

Self-imported manifest files and directory membership are selection inputs;
application source remains editable. Private workspace metadata, the virtualenv,
and the Nix GC profile live below `$XDG_CACHE_HOME/west-purifier`. Root commands
retain networking. `prefetch` prepares the environment without running a build.

For an external companion lock, use `--project` and `--lock` on purifier commands,
or set `WEST_PURIFIER_PROJECT` and `WEST_PURIFIER_LOCK` for native commands.

## Optional Nix build

The overlay provides `buildWestProject` with `src`, native West `command`,
`nativeBuildInputs`, and `installCommand`. The default command is `build` and
installation uses `cmake --install build --prefix "$out"`. The example builds a
C application through a native West extension against Nix-delivered jsmn.

The builder exposes `packages`, `tests`, `release`, and `fetches`, with known
output names available without import-from-derivation. Its release is a native
manifest-repository source archive. `west-purifier bundle` builds that archive;
`publish --tag TAG` uploads the exact archive to an existing GitHub release.

## Scope

The initial integration supports public HTTPS Git projects and imported
manifests on Linux x86-64 and ARM64. It preserves shallow Git metadata and the
native `manifest-rev` reference, including clean readonly status reporting.
History and tags beyond the locked commit are not delivered.
Submodule selection needs an additional provider. Project paths must be separate
from the manifest repository.

A full Zephyr build also needs its board toolchain and Python extension
dependencies; those need additional providers. This integration locks West's
source projects. It does not claim a complete Zephyr SDK or hardware workflow.
Python packages installed into the writable virtualenv are ordinary development
dependencies; use a Python purifier when those also need locked resolution.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
