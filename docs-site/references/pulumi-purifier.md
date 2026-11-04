# pulumi-purifier

Run Pulumi with locked, Nix-resolved provider and language plugins.

From an existing Pulumi YAML project:

```sh
nix shell 'github:nix-purifiers/pulumi-purifier'
pulumi-purifier lock
pulumi preview
```

Commit `pulumi-purifier.lock.json`. The native Pulumi language host discovers the
project's required plugins. Locking captures their exact versions, archive URLs,
and hashes for Linux x86-64 and ARM64. Nix verifies the archives and replays
Pulumi's native plugin installer before writing the lock.

This integration requires the `pulumi` wrapper. It supplies immutable plugin
files through private writable plugin directories, preserving your existing
Pulumi credentials, backend selection, and global plugin cache. Without a
lockfile it warns and runs ordinary, impure Pulumi. Install it through your usual
installation method if you want it beyond `nix shell`.

Edit resource properties and use Pulumi normally:

```sh
pulumi preview
pulumi up
pulumi stack output
```

Cloud API access retains its ordinary behavior. After changing plugin selections:

```sh
pulumi-purifier lock --update
pulumi-purifier prefetch
```

The wrapper compares plugin selections through the native language host rather
than hashing the whole program. Plugin installation and removal are guarded in
the native SDK, including native child commands. Use the lock command to update
them. Private aliases and Nix GC roots live beneath
`$XDG_CACHE_HOME/pulumi-purifier`.

Use `--project` and `--lock` for explicit locations, or set
`PULUMI_PURIFIER_PROJECT` and `PULUMI_PURIFIER_LOCK`. The native wrapper also
honors Pulumi's `--cwd` option.

## Optional Nix preparation

The overlay exposes `buildPulumiProject` with `src`, `doCheck`, and `checkCommand`.
It verifies native plugin discovery and prepares a source tree with plugins in
`.pulumi-purifier/plugins`. It exposes `packages`, `tests`, `release`, and
`fetches`; output names are known without import-from-derivation.

`pulumi-purifier bundle` creates `project.tar.gz` containing the project sources
and native plugin tree. It contains no deployment state or credentials generated
by the purifier. To use an extracted bundle with an ordinary Pulumi CLI, copy
its plugin tree into a private writable Pulumi home:

```sh
mkdir -p .consumer-pulumi/plugins
cp -r .pulumi-purifier/plugins/. .consumer-pulumi/plugins/
chmod -R u+w .consumer-pulumi
export PULUMI_HOME="$PWD/.consumer-pulumi"
pulumi preview
```

Authenticate or select your backend in that private home as appropriate.
`publish --tag TAG` uploads the exact source archive to an existing GitHub release.

## Scope

The initial provider supports Pulumi YAML projects and binary plugins from public
HTTPS archives on Linux x86-64 and ARM64. Source-based plugins and other language
runtimes need their language dependency providers. Tests use Pulumi's local state
backend and the real Random provider; they do not create cloud resources.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
