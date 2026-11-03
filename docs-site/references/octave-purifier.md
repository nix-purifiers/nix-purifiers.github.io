# octave-purifier

Locked, Nix-resolved Octave packages.

## Quickstart

```sh
nix shell 'github:nix-purifiers/octave-purifier'
octave-purifier lock control signal
octave-cli --eval 'pkg load signal; disp(upfirdn(42, 1));'
```

Octave's native package index selects the source archives. Nix compiles them
for the pinned Octave SDK. Your programs run in their working tree, with a
private package registry and readonly dependencies.

Without a lockfile, the wrappers warn and run ordinary, impure Octave. A stale
or invalid lock fails. Commit `octave-purifier.lock.json` and refresh it with
`octave-purifier lock --update`. Install the wrappers through your normal Nix
configuration if desired.

## Developing a package

A project with a native `DESCRIPTION` can build its own code outside Nix:

```sh
octave-purifier lock control signal
octave-cli --eval 'pkg install .'
octave-cli --eval 'pkg load purifierproof; purifier_answer()'
```

Use your package's name and functions in the final command. Its source package
is compiled by Octave's ordinary installer into `.octave-purifier/`. Reinstall
after changing native source. Changes to `DESCRIPTION` require relocking.

The native manager checks dependency requirements but does not automatically
select missing packages. List those packages in the lock command, as with
ordinary `pkg install`. Their native dependency declarations remain authoritative.

## Commands

```sh
octave-cli --eval 'pkg list'
octave-purifier prefetch
octave-purifier exec -- your-command
octave-purifier bundle
octave-purifier publish --tag v0.1.0
```

Locked installations reuse the prepared packages. Updating or replacing package
registries requires changing the lock. Application files remain mutable.
`bundle` creates a source archive consumed by ordinary `pkg install`;
`publish` uploads those exact bytes to an existing GitHub release.

Use `--input path` to track additional selection inputs. `--project` and `--lock`
support an external companion; native commands accept `OCTAVE_PURIFIER_PROJECT`
and `OCTAVE_PURIFIER_LOCK`. Environment profiles keep the packages and wrapper
SDK reachable by Nix garbage collection.

## Building with Nix

An optional definition can use the overlay's named builder:

```nix
pkgs.octave-purifier.buildOctaveProject {
  src = ./.;
  doCheck = true;
  checkCommand = "octave-cli --quiet test.m";
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`packageOverrides` supplies package-specific build changes. Nixpkgs recipes
provide native prerequisites; newly released versions may need overrides.

The initial target is Octave 11 on Linux. Interpreter versions, native module
ABI and external C/Fortran libraries must match. Git development snapshots and
unrelated downloads performed by application code are outside this adapter.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
