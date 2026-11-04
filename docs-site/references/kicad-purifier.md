# kicad-purifier

Run KiCad with locked, Nix-resolved Python plugins.

## Quickstart

```sh
nix shell 'github:nix-purifiers/kicad-purifier'
```

Add `kicad-purifier.json` to the project:

```json
{
  "plugins": ["org.openscopeproject.InteractiveHtmlBom"]
}
```

```sh
kicad-purifier lock --update
pcbnew board.kicad_pcb
```

Commit the selection and `kicad-purifier.lock.json`. KiCad's native PCM metadata
decoder, version compatibility checks and archive extractor prepare the selected
plugins. Nix supplies their immutable code. KiCad retains its native plugin loader;
the wrapper restricts its dependency paths to the locked tree and SDK plugins.

The `kicad`, `pcbnew`, `kicad-cli` and `kicad-python` wrappers use a private
`.kicad-purifier/` profile. Host preferences and caches remain writable; the PCM
package tree and its registration stay in Nix. Without a lockfile the wrappers
warn and run the ordinary tool. The wrappers are required for this integration.

`kicad-python` provides the SDK's Python interpreter with `pcbnew` and the locked
plugin modules. For example, `kicad-python build.py` runs the headless HTML BOM
export in `examples/minimal`. Use `kicad-purifier prefetch` to prepare dependencies
without launching an application.

Run from the project or a descendant directory. Set `KICAD_PURIFIER_PROJECT` and
`KICAD_PURIFIER_LOCK`, or pass `--project` and `--lock` before adapter subcommands,
to select another project or lockfile.

Dependency preparation reads the selection and lock without copying the working
tree into Nix. Project files enter the store only for an explicit Nix build.

## Scope

The initial provider uses KiCad 10.0 on Linux with SWIG Python code plugins from
the official PCM repository. It chooses compatible stable versions and verifies
the repository digest, archive digest, package identity and archive version.
Native package registration pins each selected plugin.

IPC plugins and their managed Python virtual environments, additional Python
requirements, custom repositories, authenticated downloads and content-only PCM
packages need additional providers. The initial SDK includes standard symbol and
footprint libraries; stock 3D model libraries are separate. Plugin-owned files
inside installation directories are immutable; project-local plugin settings can
remain beside the project.

Change dependencies with `kicad-purifier lock --update`. The native PCM cannot
replace code or registration in the locked Nix tree. Mutable profile scripting
paths are excluded from the loader, and unexpected plugin code or changed package
registration in the private profile fails closed. Ordinary project networking
remains available. Existing global KiCad profiles are separate.

## Build and release

The optional `buildKicadProject` Nix builder runs `build.py` with the same SDK and
locked plugins. Write outputs to `KICAD_PURIFIER_OUTPUT`. The example exports a
self-contained interactive HTML BOM from a native board file. The builder exposes
the environment, project outputs, checks, release archive and fetch metadata.

```sh
kicad-purifier build
kicad-purifier bundle
kicad-purifier publish --tag TAG
```

`bundle` creates `kicad-project.tar.gz`; `publish` uploads that exact archive to a
GitHub release.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
