# lazy-purifier

Use lazy.nvim with Git plugins resolved and locked by Nix.

For an existing Neovim configuration using lazy.nvim:

```sh
nix shell 'github:nix-purifiers/lazy-purifier'
lazy-purifier lock
nvim
```

Commit the native `lazy-lock.json` and `lazy-purifier.lock.json` in your Neovim
configuration repository. The first lock command uses lazy.nvim's own resolver
in a private cache. Nix verifies the selected Git sources; a fresh Neovim process
loads those sources before either lockfile is replaced.

This integration requires the Neovim wrapper. It supplies the pinned lazy.nvim
manager, readonly plugin sources, and private writable caches and state. The
usual `stdpath("data") .. "/lazy/lazy.nvim"` bootstrap works with this setup.
Without a companion lock, the wrapper warns and runs ordinary, impure Neovim.
Install it using your usual installation method if you want it available beyond
`nix shell`.

```sh
lazy-purifier lock --update
lazy-purifier prefetch
nvim --headless '+lua print(vim.version().major)' +qa
```

Configuration settings remain editable. The integration checks lazy.nvim's
native parsed dependency selection before plugin activation, so changing an
unrelated setting does not require relocking. Changed plugin URLs or version
selection require a lock update. `:Lazy log`, loading, help and normal editor
commands work; operations that mutate plugin installations require
`lazy-purifier lock --update`.

By default the integration uses the native Neovim configuration directory and
`NVIM_APPNAME`. Use `--project PATH` for another configuration with `init.lua`;
set `LAZY_PURIFIER_PROJECT` when launching its editor. `--lock` and `--native-lock`
accept external companion and native lockfiles. The corresponding environment
variables are `LAZY_PURIFIER_LOCK` and `LAZY_PURIFIER_NATIVE_LOCK`.

SDK profiles and Nix GC roots live below `$XDG_CACHE_HOME/lazy-purifier`.
Editor caches, plugin state and bootstrap links are private; existing plugin
checkouts are preserved. Root commands retain networking.

## Optional Nix build

The overlay provides `buildLazyProject` with `src`, `nvimArgs`, `doCheck`, and
`checkCommand`. It starts native headless Neovim against the Nix plugin tree.
Pass commands without a final quit command; the builder checks errors and quits.

The builder exposes `packages`, `tests`, `release`, and `fetches`, with known
output names available without import-from-derivation. Its release is a native
Neovim configuration source archive. `lazy-purifier bundle` builds the archive;
`publish --tag TAG` uploads the exact archive to an existing GitHub release.

## Scope

The initial implementation supports public HTTPS Git plugins with Lua-only
profiles on Linux x86-64 and ARM64. Local plugins, build hooks, automatic build
scripts, Git submodules and rockspec dependencies need additional providers.
Rocks are disabled in this integration. Conditional profiles must select the
same dependencies when locked and launched. Project-local `.lazy.lua` additions
are subject to the same native selection check.

The manager is part of the Nix SDK. Git history and tags beyond the locked
plugin commit are not delivered. Other plugin managers and external language
servers are outside this lock's scope.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
