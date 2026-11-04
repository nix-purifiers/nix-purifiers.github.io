# qgis-purifier

Run QGIS with locked, Nix-resolved Python plugins.

## Quickstart

```sh
nix shell 'github:nix-purifiers/qgis-purifier'
```

Add `qgis-purifier.json` to the project:

```json
{"plugins": ["latlontools"]}
```

```sh
qgis-purifier lock --update
qgis my-project.qgz
qgis_process list
```

Commit the selection and `qgis-purifier.lock.json`. QGIS's native plugin manager
selects compatible stable plugins and resolves their declared plugin dependencies.
Nix fetches the archives; QGIS's own archive installer and metadata reader prepare
immutable plugin code. Preferences and caches remain writable in the project's
private `.qgis-purifier/` profile.

The `qgis` and `qgis_process` wrappers are required. Without a lockfile they warn
and run ordinary QGIS. Use `qgis-purifier prefetch` to prepare the locked
environment without opening the application. Install the wrappers through your
usual Nix configuration if you want them available beyond `nix shell`.

Run from the project or a descendant directory. Set `QGIS_PURIFIER_PROJECT` and
`QGIS_PURIFIER_LOCK`, or pass `--project` and `--lock` before adapter subcommands,
to select another project or lockfile.

Dependency preparation reads the selection and lock without copying the working
tree into Nix. Project files enter the store only for an explicit Nix build.

## Scope

The initial provider uses QGIS 4.2 on Linux and the official stable Python plugin
repository. The pinned SDK includes pyproj. Other Python requirements need Nix
providers; the adapter does not run pip. Experimental plugins, custom repositories,
native plugins and extension-created dependency managers need additional providers.
Plugin runtime compatibility must be checked by the project; catalog compatibility
does not guarantee every plugin's Python imports work with the selected SDK.

Native plugin install, upgrade, uninstall and ZIP installation operations are
disabled in locked sessions. Enabling or disabling a locked plugin remains a
native preference. Root project networking remains available. Existing global
profiles are separate; profile override flags and executable code added to the
private profile fail closed.

## Build and release

The optional `buildQgisProject` Nix builder runs the project's `build.py` in QGIS's
processing runtime. Write outputs to `QGIS_PURIFIER_OUTPUT`, as in
`examples/minimal`, which converts CSV coordinates to GeoJSON using Lat Lon Tools.
The builder exposes the environment, project outputs, checks, release archive and
fetch metadata.

```sh
qgis-purifier build
qgis-purifier bundle
qgis-purifier publish --tag TAG
```

`bundle` creates `qgis-project.tar.gz`; `publish` uploads that exact archive to a
GitHub release. Choose reproducible native export formats for project artifacts.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
