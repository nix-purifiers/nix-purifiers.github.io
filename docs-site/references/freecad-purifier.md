# freecad-purifier

Run FreeCAD with locked, Nix-resolved workbench add-ons.

## Quickstart

```sh
nix shell 'github:nix-purifiers/freecad-purifier'
```

Add `freecad-purifier.json` to the project:

```json
{
  "addons": ["fasteners"]
}
```

```sh
freecad-purifier lock --update
FreeCAD my-project.FCStd
```

Commit the selection and `freecad-purifier.lock.json`. The native Addon Manager
selects compatible workbenches and follows their dependency declarations. Its
Git installer supplies exact source commits, and Nix supplies the immutable
workbench code. The wrapper activates those modules in a private native profile.

Use `FreeCADCmd build.py` for headless scripts. `freecad-purifier prefetch`
prepares the environment without opening the application. The wrappers are
required for the integration; without a lockfile they warn and run ordinary
FreeCAD. Preferences, macros and caches remain writable under
`.freecad-purifier/`; dependency code remains in Nix.

Run from the project or a descendant directory. To select another project or
lock location, set `FREECAD_PURIFIER_PROJECT` and `FREECAD_PURIFIER_LOCK`, or
pass `--project` and `--lock` before an adapter subcommand. Native command
arguments and working directories are preserved.

## Scope

The initial provider uses FreeCAD 1.1.4 on Linux. It supports workbench add-ons
with public HTTPS Git sources in FreeCAD's official catalog. Git submodules are
pinned with their parent source. FreeCAD's native metadata reader, compatibility
checks, dependency traversal and installation code remain in use.

Python dependencies must be supplied by the pinned FreeCAD SDK. Missing or
incompatible providers fail before a new lock is written. Zip-only add-ons,
standalone macros, preference packs, bundles, authenticated sources and
extension-created dependency managers need additional providers.

Change the selection and run `lock --update` to change dependencies. Native
Addon Manager install, update, uninstall and Python installation operations
are disabled in a locked profile. Ordinary project networking remains available.
Existing global FreeCAD profiles are separate from the project profile.

## Build and release

The optional `buildFreecadProject` Nix builder runs the project's `build.py` in
the sandbox. Write outputs to `FREECAD_PURIFIER_OUTPUT`, as in
`examples/minimal`. It exposes the native environment, project outputs, a checks
derivation, a release directory and fetch metadata. The example uses BREP for
reproducible geometry export.

```sh
freecad-purifier build
freecad-purifier bundle
freecad-purifier publish --tag TAG
```

`bundle` produces `freecad-project.tar.gz`; `publish` uploads that exact archive
to a GitHub release. Native project formats can carry timestamps and other
variable metadata; choose an export format suitable for reproducible artifacts.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
