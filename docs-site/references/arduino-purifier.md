# arduino-purifier

Compile Arduino sketches with locked, Nix-resolved cores, tools, and libraries.

From a sketch with a pinned native `sketch.yaml` profile:

```sh
nix shell 'github:nix-purifiers/arduino-purifier'
arduino-purifier lock
arduino-cli compile
```

Commit `arduino-purifier.lock.json` and `arduino-purifier.indexes/` alongside
`sketch.yaml`. The index directory preserves exact compressed, signed catalog
snapshots when upstream index URLs change. Arduino CLI's own
profile parser, platform resolver, signed indexes, and installers select the
artifacts for Linux x86-64 and ARM64. Nix verifies and replays those downloads
before the lock is written.

The `arduino-cli` wrapper is required. It supplies readonly Nix profiles through
private Arduino data, download, sketchbook, and build-cache directories. Existing
global cores and libraries are preserved. Without a lockfile it warns and runs
the ordinary, impure Arduino CLI. Install the wrapper through your usual
installation method if you want it beyond `nix shell`.

A native profile declares the board and dependency versions, for example:

```yaml
default_profile: uno
profiles:
  uno:
    fqbn: arduino:avr:uno
    platforms:
      - platform: arduino:avr (1.8.6)
    libraries:
      - ArduinoJson (7.4.3)
```

Keep editing your sketch and using native commands:

```sh
arduino-cli compile
arduino-cli compile --profile uno
arduino-cli upload --profile uno --port /dev/ttyACM0
```

The wrapper checks the dependency profile through Arduino's native parser.
Source edits, build properties, notes, and port settings do not require relocking.
After changing dependency selections:

```sh
arduino-purifier lock --update
arduino-purifier prefetch
```

Native dependency installation and removal direct you to the lock command.
Project commands retain their ordinary network access. Private mutable state and
Nix GC roots live beneath `$XDG_CACHE_HOME/arduino-purifier`.

`--project` and `--lock` select explicit locations; their environment equivalents
are `ARDUINO_PURIFIER_PROJECT` and `ARDUINO_PURIFIER_LOCK`. The native wrapper
also recognizes a sketch path passed to the command when no project is selected.

## Optional Nix build

Apply the overlay and use `buildArduinoProject` with `src`, `doCheck`, and
`checkCommand`. Its result exposes `packages`, `tests`, `release`, and `fetches`,
with output names known without import-from-derivation. The builder preserves
the sketch directory name and compiles each locked profile.

`arduino-purifier bundle` creates `firmware.tar.gz` with native HEX and ELF files
for each profile. `publish --tag TAG` uploads that exact archive to an existing
GitHub release.

## Scope

The initial provider supports pinned Arduino AVR profiles and registry libraries
on Linux x86-64 and ARM64. It captures the native indexes, core, compiler, upload,
discovery, monitor, and preprocessing tools. Source libraries, unpinned system
platforms, other cores, and additional external runtimes need providers.

Nix patches the downloaded host executable loaders. Nixpkgs' all-target GDB
replaces the obsolete bundled AVR debugger; its provider and version are recorded
in the environment metadata. Native installation metadata is normalized only to
stabilize the order of tool definitions emitted from native Go maps.

Compilation and firmware inspection are tested without hardware. Physical
uploads, monitoring, and on-device execution need your configured board.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
