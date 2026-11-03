# ansible-purifier

Lock Galaxy collections with Nix, then use Ansible in your working tree.

```sh
nix shell 'github:nix-purifiers/ansible-purifier'
ansible-purifier lock
ansible-playbook -i inventory playbook.yml
```

Put collection requirements in `requirements.yml`. For example:

```yaml
collections:
  - name: community.general
    version: 14.0.0
```

`lock` uses Ansible's native resolver and verifies its downloaded artifacts.
Commit `requirements.yml` and `ansible-purifier.lock.json`. Run
`ansible-purifier lock --update` after changing collection requirements.
Use `--requirements collections/requirements.yml` for another native filename;
`--input FILE` also locks selection inputs used by your configuration.

The wrappers supply readonly Nix collections, a private writable Ansible session,
and the pinned Ansible interpreter. Native playbooks, inventories, filters,
modules and editor commands keep their normal interfaces. Project playbooks and
local plugins remain editable. Collection lookup uses the locked collection tree;
ambient Python packages, user collection directories and a project's downloaded
`collections/ansible_collections` tree cannot shadow it. `ansible.cfg`, when
present, is a selection input. Target hosts and playbook tasks retain networking.

Without a lockfile, the wrappers print a warning and run ordinary, impure Ansible.
You can install the wrappers using your usual installation method; the quickstart
uses a temporary `nix shell`.

```sh
ansible-purifier prefetch
ansible-purifier exec -- ansible-doc \
  -t filter community.general.to_seconds
```

Run from a subdirectory normally. For a separate companion lock, set
`ANSIBLE_PURIFIER_PROJECT` and `ANSIBLE_PURIFIER_LOCK`, or use `--project` and
`--lock` with purifier commands. Runtime session state and its Nix GC profile
live below `$XDG_CACHE_HOME/ansible-purifier`.

## Optional Nix build

A project or packaging repository can call `buildAnsibleProject` from the overlay
with `src`, `playbook`, and `inventory`. Its project output runs a playbook in the
sandbox; use this for local, deterministic build tasks. Deployment tasks need
normal host access and belong in your working-tree workflow.

The builder exposes `packages`, `tests`, `release`, and `fetches`, with known
output names available without import-from-derivation. The release output is a
native project source archive. `ansible-purifier bundle` builds that archive;
`publish --tag TAG` uploads the exact archive to an existing GitHub release.

## Scope

The initial implementation supports public Galaxy collections on Linux x86-64
and ARM64. Native resolution selects transitive collection dependencies; native
offline installation checks that the locked artifacts satisfy them. Roles,
Git collections, private Galaxy servers, Python wheels and remote host system
packages need separate providers. A collection requiring extra Python libraries
needs an interpreter providing those libraries. The wrapper does not install
remote machine packages implicitly. In a locked project, use `lock --update`
instead of `ansible-galaxy install` or `download` to change dependencies.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
