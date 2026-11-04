# anki-purifier

Use Anki with locked, Nix-resolved add-ons.

## Quickstart

Enter a shell with the wrapper:

```sh
nix shell 'github:nix-purifiers/anki-purifier'
```

Create `anki-purifier.json` in your working directory with AnkiWeb add-on IDs:

```json
{"addons": [2055492159]}
```

Lock the selection, then open Anki:

```sh
anki-purifier lock --update
anki
```

The wrapper keeps Anki's normal profiles and collections. Selected add-on code
comes from the Nix store; add-on preferences and `user_files` remain writable.
Close Anki before switching a collection to a different lock. Anki's native
collection lock prevents two processes from opening the same collection.

Without a lockfile, `anki` warns and delegates to ordinary Anki. A stale or
invalid lock fails with a repair message.

## Updating add-ons

Edit the selection and capture a new lock:

```sh
anki-purifier lock --update
```

Locked sessions disable native add-on installation, removal and update checks.
Configuration and enable/disable controls remain available. Ordinary networking,
including AnkiConnect requests, remains available.

## Scripted workflows

Run an Anki Python script after profile initialization and add-on loading:

```sh
anki-purifier run build.py
```

This command uses a separate collection in `.anki-purifier/run/profile`, leaving
your normal collection alone. Use `run --gui build.py` for a visible window.
Scripts can import `aqt` and use `aqt.mw` and the selected add-ons. Script exit
status is preserved and Anki closes through its native shutdown path.

Optional `anki-purifier.settings.json` supplies add-on configuration overrides.
For example, the included AnkiConnect fixture requests an available local port:

```json
{"2055492159": {"webBindPort": 0}}
```

The example creates a note through AnkiConnect and exports native tab-separated
text. Change `answer.json` and rerun to update the export.

```sh
cd examples/minimal
anki-purifier run build.py
cat output/notes.txt
```

## Nix builds

`buildAnkiProject` is available through the flake overlay for projects that also
want to execute an Anki script in the Nix sandbox. It provides dependency,
project and release outputs. `anki-purifier build` builds the project output;
`anki-purifier bundle` creates a normalized release archive.

## Scope

The integration uses Anki's native AnkiWeb downloader, archive installer and
metadata handling. Captured archives are hashed and fetched by Nix. Runtime
guards reject writable add-on code and freeze native code installation paths;
they do not sandbox arbitrary Python code executed by an add-on or project.

The pinned SDK is Anki 26.09.3. Native GUI, add-on and export checks run on
x86_64 Linux. The flake also configures aarch64 Linux; its runtime has not been
tested locally. Typed projection interfaces are unsupported.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
