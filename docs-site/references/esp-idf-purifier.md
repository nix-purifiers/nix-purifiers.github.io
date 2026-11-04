# esp-idf-purifier

Locked, Nix-resolved components for ESP-IDF.

## Quickstart

In an ESP-IDF project configured for ESP32-C3:

```sh
nix shell 'github:nix-purifiers/esp-idf-purifier'
esp-idf-purifier lock --update --target esp32c3
idf.py build
```

Commit `esp-idf-purifier.lock.json` and the native `dependencies.lock`.
The `idf.py` wrapper is required for locked component resolution. Without a
purifier lock, it warns and runs the ordinary SDK with impure component
resolution. Install it with your usual method when you want it beyond the
temporary shell.

Native commands use your working tree and build directory. Installed components
live in Nix; private aliases and a GC root live in `.esp-idf-purifier/`. Existing
`managed_components` caches are preserved and ignored. Source edits keep the
same pins, and unchanged builds retain Ninja's incremental behavior.

Use `esp-idf-purifier prefetch` to realize and validate the current selection.
Use `esp-idf-purifier lock --update` to refresh dependencies. `--project PATH`
and `--lock PATH` select a project and an external companion lock. Native
`idf.py -C PATH ...` commands retain their usual project selection.

## Scope

The initial SDK provider supports ESP32-C3 and Linux targets on Linux x86-64 and
ARM64 hosts. Native ARM64 checks are configured separately. It includes the SDK,
Python environment, ESP32-C3 compiler and ROM metadata. Debuggers, OpenOCD and
additional hardware toolchains are separate tools.

The component provider supports the public ESP Component Registry. Espressif's
native parser, solver, installer and content checks remain responsible for
component identities. Archive bytes and checksum files are hash-pinned in Nix;
registry indexes are native partial-mirror snapshots.

Git and local dependency sources, authenticated registries and dependencies
conditional on Kconfig settings require additional providers and are rejected.
The SDK source includes the framework dependencies exercised by the ESP32-C3
Wi-Fi fixture; Bluetooth and other unprovided framework submodules need SDK
providers. Root project code retains ordinary network access.

## Nix builds and releases

The overlay exposes:

```nix
pkgs.esp-idf-purifier.buildEspIdfProject {
  src = ./.;
}
```

The result provides `packages.environment`, `packages.project`, `tests`,
`release` and `fetches`. Options include `lockFile`, `fetchers`, `doCheck` and
`checkCommand`. The project output contains the native ELF and flashing files;
`release` contains `firmware.tar.gz`. Linux target builds produce their ELF.

```sh
esp-idf-purifier build
esp-idf-purifier bundle
esp-idf-purifier publish --tag v1.0.0
```

Publishing uploads the exact bundle to an existing GitHub release using your
`gh` authentication. Native `esptool` consumes the exported image files.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
