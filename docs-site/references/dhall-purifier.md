# dhall-purifier

Locked, Nix-resolved imports for Dhall.

## Quickstart

```sh
nix shell 'github:nix-purifiers/dhall-purifier'
dhall-purifier lock --file package.dhall
dhall-to-json --file package.dhall
```

Locking runs Dhall's native freeze command on the selected file and its local
imports, adding integrity checks to remote imports. Commit those files and
`dhall-purifier.lock.json`. Nix realizes the checked imports as native semantic
cache entries. Your local expressions remain editable.

The shell provides `dhall`, `dhall-to-json`, `json-to-dhall` and
`dhall-lsp-server` wrappers. Without a lockfile, they warn and run the ordinary,
impure tools. Invalid or stale locks fail. The wrappers can also be installed
through your normal Nix configuration.

## Development

```sh
dhall --file package.dhall
dhall-to-json --file package.dhall
dhall-lsp-server
```

Source edits do not require relocking. Changes to import declarations do:

```sh
dhall-purifier lock --update
```

Locked tools use HTTP-disabled builds and a private cache under
`.dhall-purifier/`. Dependency cache entries point to readonly Nix outputs.
Editors use the same environment through the language-server wrapper.

```sh
dhall-purifier prefetch
dhall-purifier exec -- your-command
```

Repeat `--file` when capturing several entry points. `--input path` tracks extra
selection files. Use `--project` and `--lock` for an external companion; wrappers
accept `DHALL_PURIFIER_PROJECT` and `DHALL_PURIFIER_LOCK`. Environment generations
retain their dependency and frontend closures for garbage collection.

The initial integration targets Dhall 1.42.3 on Linux. Local code imports must
stay within the project. Environment imports and custom HTTP headers are
unsupported. `--no-cache` bypasses the prepared semantic cache and cannot fetch
remote imports in locked commands.

## Publication

```sh
dhall-purifier bundle
dhall-purifier publish --tag v0.1.0
```

Publication uploads an importable, normalized `source.dhall` and an archive
containing the native source, binary expression and semantic cache. Ordinary
Dhall can consume the source without the wrapper.

## Building with Nix

An optional definition can use the overlay's named builder:

```nix
pkgs.dhall-purifier.buildDhallProject {
  src = ./.;
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
The imports' fetch hashes cover Dhall's canonical binary encodings. A fixed-output
Nix derivation runs the native resolver and checks both those bytes and Dhall's
integrity checks.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
