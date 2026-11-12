# Purifier releases

Repositories call the pinned reusable `purifier-release.yml` workflow after
their `check` workflow succeeds on main. Manual runs use the same CI gate.
Only the current main commit can be tagged; a superseded run leaves release
publication to the newer commit's CI.

The gate makes up to six read-only queries, two seconds apart, because a
successful workflow event may precede its visibility in the run-list API.
Every query still requires a completed successful main push/manual run for the
exact commit. An absent, failed, cancelled, skipped, unfinished, wrong-commit or
pull-request result never authorizes publication. This does not retry release
creation or artifact uploads.

Versions increment within a `MAJOR.MINOR` series, starting at `0.1.1`.
Native package builds receive that version as an explicit Nix package override
from a content-locked source snapshot. Publishing does not rewrite a source
version file or commit a version bump. Source builds use a development version
that identifies their source contents.
The release manifest fingerprints tracked implementation files and locked
dependencies. Documentation, tests and workflow-only changes do not create
another release. Changing the series starts a new series at revision 1.

Every release includes a source archive, a manifest and SHA-256 checksums.
Native integrations additionally include `native-repository.zip`:

| Kind | Integration | Pages path |
|---|---|---|
| python | PDM and Poetry plugins | `simple/<project>/` |
| yarn | Yarn Berry plugin | `plugins/<version>/purifier.cjs` |
| maven | Maven recording extension | `maven/` |
| ant | Ant native integration, consumed by Maven-compatible Ivy resolvers | `maven/` |
| source | Wrappers and Nix libraries | GitHub release assets |

The native package sites are regenerated from all immutable release assets,
preserving old versions. The site build merges them with the documentation;
it never deploys documentation over an existing package repository. A native
release explicitly dispatches the Pages workflow because GitHub does not
start another workflow for release events made using `GITHUB_TOKEN`.

The Maven extension is a download recorder, not a replacement for the
`maven-purifier` wrapper. Gradle also needs its wrapper and has no independent
plugin package to publish. Other wrapper-based tools use tagged flakes.

Run `python3 -m unittest discover -s release -v` to check release policy,
repository indexes and published plugin bootstrapping.
