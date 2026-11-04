# joplin-purifier

Use Joplin with locked, Nix-resolved plug-ins.

## Quickstart

Start a shell with the integration:

```sh
nix shell 'github:nix-purifiers/joplin-purifier'
```

Create `joplin-purifier.json` in your working directory:

```json
{
  "plugins": ["io.github.jackgruber.combine-notes"]
}
```

Capture the native Joplin catalog selection, then launch Joplin:

```sh
joplin-purifier lock --update
joplin-desktop
```

Commit the selection and `joplin-purifier.lock.json`. Later launches reuse the
locked archives. Close an existing Joplin instance before launching the locked
one: an occupied profile is refused rather than forwarded to another process.

The desktop wrapper retains your normal profiles, notes and preferences. Plug-in
code comes from the immutable environment; plug-in data and settings remain
writable. Joplin's bundled plug-ins are retained. Installation, updates, deletion
and development plug-in paths are disabled while the lock applies. Ordinary
network access, including note synchronization, remains available.

Without a lockfile, the wrapper prints a warning and starts ordinary Joplin.
A malformed or stale lock fails with an instruction to update it.

## Updating

Edit the selection, then explicitly resolve it again:

```sh
joplin-purifier lock --update
```

Capture uses Joplin's native repository client, compatibility checks, archive
parser and installer. The lock records the selected release URLs, hashes and
native metadata. Resolution verifies installation before replacing the lock.

## Scripted projects

The example combines two notes with the real Combine Notes plug-in and exports
Markdown through Joplin's native exporter:

```sh
cd examples/minimal
joplin-purifier run build.cjs
cat output/combined.md
```

A script exports an asynchronous function receiving Joplin's `app`, `Setting`,
`Note`, `Folder`, `pluginService`, `commands` and `interop` objects. It runs after
native startup and can return an integer exit status. Scripted runs use a private
profile under `.joplin-purifier/run`, isolated from your desktop notes.

## Nix builds

`joplin-purifier build` builds the scripted project in the Nix sandbox.
`joplin-purifier bundle` produces a deterministic archive of its outputs.
External Nix definitions can use `buildJoplinProject` from the supplied overlay;
its arguments include `src`, `lockFile` and `script` (default `build.cjs`).

## Support

The current provider targets Joplin Desktop 3.7.21 on x86_64 Linux. It patches
the pinned application bundle at checked locations and uses its original native
modules. Other SDK versions require validating a new provider.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
