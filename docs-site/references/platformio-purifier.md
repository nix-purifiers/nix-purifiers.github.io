# platformio-purifier

Build PlatformIO projects with packages resolved and locked by Nix.

From an existing Arduino AVR project with `platformio.ini`:

```sh
nix shell 'github:nix-purifiers/platformio-purifier'
platformio-purifier lock
pio run
```

Commit `platformio-purifier.lock.json`. Locking uses PlatformIO's own registry
resolver and package installer for both supported host architectures. It captures
the platform, toolchain, frameworks, transitive libraries, uploader, test framework,
and configured analysis tools. Nix verifies the archives and replays the native
installer before the lock is written.

This integration requires the `pio` and `platformio` wrappers. They supply readonly
Nix package trees through private writable PlatformIO state. Existing `.pio`
dependency caches and global installations are preserved. Without a lockfile,
the wrappers warn and run ordinary, impure PlatformIO. Install them through your
usual installation method if you want them beyond `nix shell`.

Edit your sources and use the normal commands:

```sh
pio run
pio test
pio check
pio run --target upload
```

Tests and uploads use your configured hardware normally. For a test firmware
compile without uploading or running it:

```sh
pio test --without-uploading --without-testing
```

Dependency selections are checked through PlatformIO's native configuration
parser. Source edits and build flags do not require relocking. After changing
dependency declarations:

```sh
platformio-purifier lock --update
platformio-purifier prefetch
```

Native package update and removal operations direct you to the lock command.
Build outputs stay in the project's usual build directory. Package aliases,
private caches, and Nix GC roots live beneath
`$XDG_CACHE_HOME/platformio-purifier`. Project commands retain networking.

`--project`, `--config`, and `--lock` accept explicit locations. Their environment
equivalents are `PLATFORMIO_PURIFIER_PROJECT`, `PLATFORMIO_PURIFIER_CONFIG`, and
`PLATFORMIO_PURIFIER_LOCK`. The native wrappers also honor `--project-dir` and
`--project-conf` where the underlying command supports them.

## Optional Nix build

The overlay exposes `buildPlatformioProject` with `src`, `configFile`, `doCheck`,
and `checkCommand`. It exposes `packages`, `tests`, `release`, and `fetches`;
output names are known without import-from-derivation.

`platformio-purifier bundle` produces an archive containing the native firmware
HEX and ELF files for each locked environment. `publish --tag TAG` uploads that
exact archive to an existing GitHub release.

## Scope

The initial provider supports public registry and HTTPS archive packages for
Arduino AVR projects on Linux x86-64 and ARM64. The SDK patches host executable
loaders for Nix. It supplies Nixpkgs' all-target GDB in place of the old bundled
AVR debugger, and Nixpkgs cppcheck replaces the registry analyzer that crashes
on ARM64. These providers and versions are recorded in the environment metadata.

Native resolution, firmware compilation, Unity test-firmware compilation, and
firmware inspection are tested without a board. Physical uploads and on-device
test execution require your hardware. Other platforms, Git or local package
sources, and additional Python dependencies need their own providers.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
