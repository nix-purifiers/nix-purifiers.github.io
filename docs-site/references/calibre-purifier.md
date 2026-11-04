# calibre-purifier

Locked, Nix-resolved calibre plugins, with writable book libraries and preferences.

## Quickstart

From the directory where you want to keep the plugin selection:

```sh
nix shell 'github:nix-purifiers/calibre-purifier'
```

Create `calibre-purifier.json` with plugin names from calibre's catalog:

```json
{"plugins": ["EpubMerge"]}
```

Capture the lock and start calibre:

```sh
calibre-purifier lock --update
calibre
```

The shell provides calibre's normal commands, including `calibre-debug`,
`calibredb`, `ebook-convert` and `ebook-viewer`. Keep the selection and
`calibre-purifier.lock.json` together. Run commands from that directory or its
children, or set `CALIBRE_PURIFIER_PROJECT` to its path. The wrappers are also
installable with your usual Nix configuration.

Plugins are loaded from immutable Nix store ZIPs through calibre's system-plugin
loader. Settings and caches live in `.calibre-purifier/`; existing desktop
preferences are not imported. Choose your book library normally. Preferences,
plugin configuration and enabled/disabled state remain writable. Install or
remove plugins by editing the selection and running `lock --update`.

Without a lockfile, wrappers print a warning and run the ordinary calibre
command. A stale or invalid lock fails. Use `calibre-purifier prefetch` to prepare
dependencies without launching calibre. For a lock outside the project, use
`--lock PATH` on adapter commands or `CALIBRE_PURIFIER_LOCK` on native commands.

Dependency preparation reads the selection and lock without copying the working
tree into Nix. Project files enter the store only for an explicit Nix build.

## Build and release

The example merges two books with EpubMerge and converts the result to plain
text. Run its `build.py` with `calibre-debug --exec-file build.py` in the working
tree. For an optional Nix build:

```sh
calibre-purifier build
calibre-purifier bundle
```

`build` returns an output directory. `bundle` produces a deterministic
`calibre-project.tar.gz`; `publish --tag TAG` uploads that exact archive to an
existing GitHub release. An external Nix definition can call
`pkgs.calibre-purifier.buildCalibreProject` through the flake overlay, with `src`,
optional `lockFile`, `script`, `fetchers`, `doCheck` and `checkCommand` arguments.

## Scope

The integration uses calibre's original catalog reader, compatibility checks,
ZIP installer, initialization and system-plugin loader. The lock records the
catalog metadata and archive hashes; replay does not consult the catalog.
Capture uses calibre's bundled publisher CA to verify its official plugin site.

Native plugin installation and removal are frozen in a locked profile. Calibre's
background metadata-source Python updater is disabled because it otherwise
loads executable code from a mutable cache; built-in metadata sources and normal
application networking remain available. Mutable user-plugin registrations and
ZIPs in the private plugin directory are rejected.

Locked GUI and viewer instances use a profile-and-lock-specific process address,
so they cannot forward launches to an ordinary desktop instance. Calibre's shared
database exclusion remains active. Close an existing GUI before relaunching
with an updated lock. Run book-library operations with the usual calibre care.

Linux x86_64 and aarch64 outputs and CI are defined. Local native and GUI checks
run on x86_64; aarch64 requires its CI run. Plugin archives can include native
code or load additional code themselves; such plugin-specific providers need
separate support. This integration freezes calibre's plugin-management paths,
not arbitrary Python imports executed by a plugin or project.

EPUB output can contain generated timestamps and identifiers. The example
exports plain text for reproducible build and release checks. Native artifacts
do not implement the separate typed projection interface.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
