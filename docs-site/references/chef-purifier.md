# chef-purifier

Locked, Nix-resolved cookbook dependencies for Chef Policyfiles, using the Cinc
community distribution. Edit recipes and run native commands in your working tree.

## Quickstart

In a project with a `Policyfile.rb`:

```sh
nix shell 'github:nix-purifiers/chef-purifier'
chef-purifier lock --update
cinc-cli install
cinc-cli export ./policy
```

Commit `chef-purifier.lock.json` and `Policyfile.lock.json`. The `cinc-cli` and
`chef-cli` wrappers use private native caches backed by immutable Nix cookbooks.
They are required for locked resolution. Without a purifier lock, they warn and
run ordinary Cinc CLI commands. Install the integration with your usual method
when you want it available beyond the temporary shell.

Recipe bodies, policy attributes and run lists remain editable. Native
`cinc-cli update` refreshes project code while preserving the locked cookbook
versions. Use `chef-purifier lock --update` to change dependencies, and
`chef-purifier prefetch` to realize the current lock.

`chef-purifier --project PATH exec -- COMMAND ...` runs a Cinc CLI command in a
selected project. The native wrappers preserve the caller's working directory. Set
`CHEF_PURIFIER_PROJECT` and `CHEF_PURIFIER_LOCK` to select their project and an
external companion lock explicitly.

## Supported dependencies

The initial provider supports public HTTPS Supermarket cookbook archives and
local cookbooks inside the project. Native Cinc evaluates the Policyfile,
resolves dependencies, installs archives and checks cookbook content identities.
Cookbook gem dependencies, included policies, Git sources and authenticated
registries require additional providers and are rejected.

The integration locks cookbook resolution. Recipes execute normally, including
network requests and resource changes. Run exported policies with an ordinary
Cinc client; deployment credentials and server operation remain native concerns.

## Nix builds

The overlay exposes `pkgs.chef-purifier.buildChefProject { src = ./.; }`.
It exports the policy through Cinc, with hash-pinned cookbook archives.
`packages.environment` contains the native cookbook cache,
`packages.project` contains the exported policy, and `release` is its
reproducible `policy/` tarball. Deployment is a separate native operation.

Set `doCheck = true` and provide `checkCommand` to check the exported policy.
The checks run in its directory, with the Cinc client available. The builder
accepts `lockFile` and `fetchers` overrides.

`chef-purifier build` exports the policy; `chef-purifier bundle` creates its
archive. `chef-purifier publish --tag TAG` uploads that archive to an existing
GitHub release using your authenticated `gh` account.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
