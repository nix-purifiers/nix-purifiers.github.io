# quarto-purifier

Render Quarto documents with extensions resolved and locked by Nix.

Declare the extensions in `quarto-extensions.json`, using Quarto's normal
GitHub targets or HTTPS archive URLs:

```json
["quarto-ext/fontawesome"]
```

```sh
nix shell 'github:nix-purifiers/quarto-purifier'
quarto-purifier lock
quarto render
```

Commit the declaration and `quarto-purifier.lock.json`. Locking uses Quarto's
native resolver and installer in a private directory. Nix verifies the archive
hashes and replays the native installer before the lock is written.
Versioned targets or immutable archive URLs help keep sources available.

This integration requires the Quarto wrapper. It directs native extension
discovery to readonly Nix sources and preserves existing `_extensions` trees.
Without a lockfile, it warns and runs ordinary, impure Quarto. Install the
wrapper using your usual installation method if you want it beyond `nix shell`.

Document edits need no relocking. Change the declaration to add or remove
extensions, then run:

```sh
quarto-purifier lock --update
quarto-purifier prefetch
quarto render
```

Native extension installation and removal are disabled while the lock is active.
Other commands retain normal networking. Writable Quarto caches and Nix GC
roots are private beneath `$XDG_CACHE_HOME/quarto-purifier`.

Use `--project PATH`, `--lock PATH`, or `--declarations PATH` for external
configuration. The corresponding environment variables are
`QUARTO_PURIFIER_PROJECT`, `QUARTO_PURIFIER_LOCK`, and
`QUARTO_PURIFIER_DECLARATIONS`; they also apply to the `quarto` wrapper.

## Optional Nix build

The overlay exposes `buildQuartoProject` with `src`, `quartoArgs`, `doCheck`,
and `checkCommand`. It exposes `packages`, `tests`, `release`, and `fetches`;
output names are known without import-from-derivation.

`quarto-purifier bundle` produces a native project source archive with the
locked extensions vendored for an ordinary Quarto consumer.
`quarto-purifier publish --tag TAG` uploads that exact archive to an existing
GitHub release.

## Scope

The initial implementation supports public HTTPS extension archives and GitHub
extension targets on Linux x86-64 and ARM64. Native built-in extensions remain
part of the pinned SDK. Local and nested `_extensions` trees do not override
the declared extensions while the lock is active.

The lock covers extension sources and the Quarto SDK. Python, R, Julia, TeX,
browser downloads, remote document resources, and dependencies fetched by
extension code need their own integrations. The initial Nix check uses a
Markdown-to-HTML project without a computation engine.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
