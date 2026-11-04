# fiji-purifier

Fiji with locked, Nix-resolved plugins and a private, writable profile.

## Quickstart

Use a directory to hold the plugin selection; your images can live elsewhere.

```sh
nix shell 'github:nix-purifiers/fiji-purifier'
```

Create `fiji-purifier.json`. For example, select MorphoLibJ and its update sites:

```json
{
  "updateSites": [
    {
      "name": "Java-8",
      "url": "https://sites.imagej.net/Java-8/"
    },
    {
      "name": "IJPB-plugins",
      "url": "https://sites.imagej.net/IJPB-plugins/"
    }
  ],
  "plugins": ["plugins/MorphoLibJ_.jar"]
}
```

Capture the lock and start Fiji:

```sh
fiji-purifier lock --update
fiji
```

The shell provides the `fiji` wrapper. It discovers the selection in the current
directory or a parent; set `FIJI_PURIFIER_PROJECT` to use another directory.
Keep `fiji-purifier.json` and `fiji-purifier.lock.json` together. The wrapper is
also installable through your usual Nix configuration.

Images and project macros stay in the working tree. Preferences and caches are
writable under `.fiji-purifier/`; existing desktop preferences are not imported.
Plugin JARs, startup macros and the SDK come from Nix. Each locked launch starts
a separate instance, so it cannot forward work to an ordinary Fiji process.

Select updater filenames; the original updater chooses versions and transitive
dependencies. Site order retains its native precedence. Edit the selection and
run `lock --update` to change plugins. Bare `lock` preserves pins; `prefetch`
prepares dependencies without launching Fiji. Without a lock, the wrapper warns
and runs ordinary Fiji. Stale locks report how to repair them; invalid locks fail
before launch.
For an external lock use `--lock PATH` on adapter commands or
`FIJI_PURIFIER_LOCK` on the native wrapper.

Dependency preparation reads the selection and lock without copying the working
tree into Nix. Project files enter the store only for an explicit Nix build.

## Build and release

The example runs MorphoLibJ's native **Morphological Filters** command and exports
a TIFF. Run it in the working tree with:

```sh
fiji --headless --console -macro build.ijm output
```

Optional Nix builds use `build.ijm`, passing the output directory as its macro
argument:

```sh
fiji-purifier build
fiji-purifier bundle
```

`build` returns an output directory. `bundle` produces a deterministic
`fiji-project.tar.gz`; `publish --tag TAG` uploads that exact archive to an
existing GitHub release. External Nix definitions can call
`pkgs.fiji-purifier.buildFijiProject` through the flake overlay. It accepts `src`,
`lockFile`, `script`, `fetchers`, `doCheck` and `checkCommand`. Use checks for the
outputs your macro should produce, since ImageJ macros can report errors without
returning a failing process status.

## Scope

Capture uses the original ImageJ updater's catalog parser, platform selection,
dependency graph and conflict checks. Replay uses its original installer and
native checksums against timestamped archives fetched by Nix. The lock includes
the catalog snapshot. Replay does not consult update sites. SDK JARs with the
same native identity are replaced, avoiding competing versions on the classpath.

The integration restores the updater removed by the stock Nix Fiji package,
then freezes its update paths, the legacy plugin importer and the launcher's
remote repair-code downloader. Normal image IO, macros and project networking
remain available. Mutable home-directory plugins are excluded. Explicit external
plugin, classpath and Java-runtime overrides need additional providers.

The pinned combination is Fiji `20250514-1117`, Java 11 and ImageJ `1.54p` on
Linux x86_64. MorphoLibJ `1.6.5` is tested with native GUI and headless commands.
Other ImageJ core versions, non-JAR dependencies and extra native/JNI libraries
need providers. Plugins that run their own dependency downloaders also require
separate support. The bundled SDK's plugins remain available independently of
additional selections.

Native TIFF outputs do not implement the separate typed projection interface.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
