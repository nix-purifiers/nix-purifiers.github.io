# haxelib-purifier

Locked, Nix-resolved libraries for Haxe.

## Quickstart

Start in a project with `haxelib.json` or native `.hxml` build descriptions.

```sh
nix shell 'github:nix-purifiers/haxelib-purifier'
haxelib-purifier lock
haxelib install build.hxml
haxe build.hxml
```

The shell supplies `haxe` and `haxelib` wrappers. Each project gets a private
Haxelib repository under `.haxelib-purifier/`. Library sources come from readonly
Nix outputs; a package's own source uses Haxelib's native development-directory
integration. An existing `.haxelib/` and your global repository remain separate.

Without a companion lockfile, wrappers warn and run the ordinary native tool.
Stale or invalid locks fail. Commit `haxelib-purifier.lock.json`; refresh it after
changing dependency metadata:

```sh
haxelib-purifier lock --update
```

Source edits do not require relocking. Root `.hxml` files, their native includes
and `haxelib.json` are tracked automatically. Use `lock --input path` to track
other files that affect selection. `prefetch` prepares the immutable repository.
Wrappers can also be installed using your normal Nix configuration.

## Resolution

The pinned native Haxelib client selects versions and transitive dependencies.
The companion records its selected repository versions and current selections,
SDK identity and hashes of the exact downloaded ZIPs. Nix verifies those bytes;
Haxelib's native reader installs them and checks package names, versions and
class paths. Frozen native commands validate dependencies against that prepared
repository. They cannot resolve additional packages from the network.

This integration currently supports registry ZIPs from `lib.haxe.org`, Haxe
4.3 and Haxelib 4.1. Git, Mercurial and arbitrary package servers are outside
its current scope. Packages requiring additional native toolchains need those
supplied as Nix build inputs. SDK changes require relocking.

## Commands

```sh
haxelib-purifier exec -- haxe build.hxml
haxelib-purifier release
haxelib-purifier publish \
  --repo owner/project --tag v0.1.0
```

For packages with `haxelib.json`, `release` produces a reproducible native ZIP.
Its declared name, version and class path must match the lock. An ordinary
Haxelib user can install that ZIP. `publish` creates or updates a GitHub release
with the same bytes. Projects described only by HXML can build and run; native
package publication requires `haxelib.json`.

Use `--project` and `--lock-file` to select an external companion. Native commands
also accept `HAXELIB_PURIFIER_PROJECT` and `HAXELIB_PURIFIER_LOCK`. Environment
profiles retain both dependencies and the wrapper SDK as garbage collector roots.

## Building with Nix

An optional project Nix definition can call the overlay's
`haxelib-purifier.buildHaxeProject` through `callPackage`:

```nix
pkgs.haxelib-purifier.buildHaxeProject {
  src = ./.;
  buildCommand = "haxe build.hxml";
  checkCommand = "haxe tests.hxml";
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`packages.environment` contains the dependency repository;
`packages.project` builds the application. Override `buildCommand`,
`checkCommand`, `installCommand`, `doCheck` or `nativeBuildInputs` for the project.
The default build command is `haxe build.hxml`; the default check command is empty.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
