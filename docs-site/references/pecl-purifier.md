# pecl-purifier

Locked, Nix-resolved PHP extensions from PECL.

## Quickstart

```sh
nix shell 'github:nix-purifiers/pecl-purifier'
pecl-purifier lock yaml msgpack
php your-program.php
```

The shell supplies PHP and PECL wrappers. PECL's native resolver selects the
source packages; Nix compiles their modules and development headers for the
pinned PHP SDK. PHP loads those readonly modules while your application remains
in its working tree.

Without a lockfile, each wrapper warns and runs its ordinary, impure tool. A
stale or invalid lock fails. Commit `pecl-purifier.lock.json`; refresh selection
with `pecl-purifier lock --update`. Application source edits do not require
relocking. The wrappers can also be installed through your normal Nix setup.

## Developing an extension

For a source extension with `package.xml`, its native dependency declarations
select the packages:

```sh
pecl-purifier lock
pecl install --force package.xml
php test.php
```

The native PECL installer builds your extension outside the Nix sandbox into a
private `.pecl-purifier/` directory. PHP loads it alongside the prepared Nix
modules. Rebuild it with the same install command after changing C source.
Changes to `package.xml` require relocking.

## Native tools

```sh
pecl list
pecl info yaml
php --ri yaml
php --rf yaml_parse
pecl-purifier exec -- your-command
```

PECL uses a private native registry and cached source archives. Locked package
installation registers the prepared dependency; it does not rebuild that
dependency in the working tree. PHP's native reflection sees the loaded modules,
and their development headers remain available from Nix.

## What is locked

The companion records exact archive URLs and hashes, native package metadata
and dependency edges, tracked inputs, PHP's module API, Zend APIs, thread/debug
mode and SDK-provided modules. The build checks the actual SDK and archive
metadata again. Missing packages fail before network access.

This version supports PHP 8.5 and PECL source extensions on Linux. Nixpkgs
extension recipes supply build prerequisites; newer upstream versions can need
recipe overrides. Userland PEAR packages, custom channels and PIE are outside
the current scope. PHP configuration that replaces extension search paths is
rejected in a locked session.

Use `lock --input path` for additional selection inputs. `prefetch` prepares
dependencies. Use `--project` and `--lock` for an external companion; native
commands accept `PECL_PURIFIER_PROJECT` and `PECL_PURIFIER_LOCK`. Environment
profiles retain the modules, headers and wrapper SDK as Nix garbage collector
roots.

## Publication

```sh
pecl-purifier bundle
pecl-purifier publish --tag v0.1.0
```

An extension project produces a reproducible native PECL `.tgz`, consumed by the
ordinary PECL toolchain. A PHP application without `package.xml` produces a
source tarball. `publish` uploads the exact files to an existing GitHub release;
it does not submit a release to the PECL registry.

## Building with Nix

An optional project definition can use the overlay's named builder:

```nix
pkgs.pecl-purifier.buildPeclProject {
  src = ./.;
  doCheck = true;
  checkCommand = "php test.php";
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`packages.environment` contains the prepared modules and manifest;
`packages.project` builds the extension or packages application source.
`extensionOverrides` supplies package-specific build changes.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
