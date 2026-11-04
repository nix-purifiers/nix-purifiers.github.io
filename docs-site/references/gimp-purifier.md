# gimp-purifier

Use GIMP with locked, Nix-built plug-ins.

## Quickstart

Enter a shell with the wrappers:

```sh
nix shell 'github:nix-purifiers/gimp-purifier'
```

Create `gimp-purifier.json` with the source archives to build:

```json
{
  "plugins": [
    {
      "name": "resynthesizer",
      "url": "https://github.com/bootchk/resynthesizer/archive/v3.0.tar.gz",
      "build": "meson"
    }
  ]
}
```

Capture and validate the lock, then open GIMP:

```sh
gimp-purifier lock --update
gimp
```

Nix builds the plug-ins with GIMP's SDK and their native Meson installation.
The wrapper loads them from the Nix store. Preferences and application state
remain writable in `.gimp-purifier/profile`.

Without a lockfile, the wrappers warn and run ordinary GIMP. A stale or invalid
lock fails with a repair message. Both `gimp` and `gimp-console` are wrapped.

## Updating plug-ins

Change the source selection and recapture:

```sh
gimp-purifier lock --update
```

Capture hashes each source archive and builds the candidate environment before
replacing the existing lock. `gimp-purifier lock` preserves current pins;
`gimp-purifier prefetch` realizes the dependency environment.

## Native workflows

Open images and use GIMP normally. Native batch commands also work:

```sh
gimp-console --new-instance \
  --no-fonts --no-data \
  --batch-interpreter=python-fu-eval \
  --batch="__import__('runpy').run_path('build.py')" \
  --quit
```

The included example invokes the native Resynthesizer procedure and writes a
PPM image. Edit `size.json` to change the result.

## Nix builds

The overlay exposes `pkgs.gimp-purifier.buildGimpProject`. It runs the project's
`build.py` through GIMP's native Python batch interpreter in the Nix sandbox,
with `GIMP_PURIFIER_OUTPUT` set to the output directory. It provides dependency,
project, test and normalized release outputs.

```sh
gimp-purifier build
gimp-purifier bundle
```

## Scope

The current provider supports Meson source archives targeting GIMP 3.2.6, with
GIMP's SDK, GTK, GLib and FFTW available as build dependencies. Other build
systems or additional dependencies need providers. This is a native source
build adapter; it does not use the archived GIMP plug-in registry as a live
package manager.

Locked sessions fix the plug-in, module, interpreter, environment and Script-Fu
search paths even when preferences request different paths. Native extension
installation is frozen. New instances avoid forwarding commands to an ordinary
GIMP process. Ordinary project and plug-in networking remains available.
The wrapper controls code resolution; it does not sandbox arbitrary plug-in
or batch-script behavior.

Linux x86_64 and aarch64 are configured. Runtime verification currently runs
on x86_64. Typed projection interfaces are unsupported.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
