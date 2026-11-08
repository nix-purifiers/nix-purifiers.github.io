# Project documentation sites

## Tier evidence

Quality registry version 3 keeps technical derivation receipts separate from
reviewed human-use evidence. Tier 3 and above require a clear attributed
firsthand human report; sample-project use by a maintainer or contributor can
qualify. Tier 1 additionally needs qualitative confidence in ongoing real use.
Credible human reports and attributable maintained-consumer history can support
that review. No fixed number of users, reports or months establishes it.

`humanUseReview` records dates, subject, stated scope, reporter relationship,
primary-source or direct-attestation provenance, and explicit evidence gaps.
Direct attestations may be private. The public projection excludes private
originals and locations; reviewers inspect the actual report before acceptance.
Report excerpts and statements about local checks retain their version,
platform and sandbox limits and do not change technical compatibility evidence.
The human-use section stays within the existing collapsed criteria details.
Version 2 remains available only to explicit fixture/history helpers; production readers require version 3. Publication pairs new definitions
with reviewed version 3 assignments. See [the model](../model/README.md).

## Structured behavior model

The behavior catalog lives in `model/projects/*.nix`. It uses typed Nix
modules, with a locked dependency on `nixpkgs.lib` alone. Jekyll remains
the final Markdown renderer. The model is independent of Jekyll and exports
ordinary JSON for other tools.
It also drives the operational harness and shared behavioral tests;
see [the model and harness](../model/README.md) for the integration boundary.
Per-project prose and presentation choices live in `docs-site/projects/`.

Each project explicitly records inputs, lockfiles, integration, relocking,
missing/stale-lock behavior, native build and editor commands, platforms,
dependency sources, CLI authentication, offline scope, builder isolation,
and outputs. These declarations are authoritative. Optional implementation or
conformance-test references can record supporting evidence; generated prose
is not evidence for the facts from which it is generated.

Every field must be addressed. `unknown` and `not-applicable` require a
reason and cannot carry a value. Do not substitute `false`, an empty list,
or an inherited family default for an uninvestigated capability.

```nix
facts.relock = {
  state = "known";
  value = "preserves-pins";
};
facts.credentials = {
  state = "unknown";
  reason = "CLI authentication has not been investigated.";
};
```

The behavioral vocabulary and fact types live in `model/contract.json`.
`model/schema.nix` derives the Nix option types from it. Section order,
shared text, and template applicability conditions live in the separate
documentation `contract.json`. The documentation export combines the two
contracts for validation at the JSON boundary.

Section titles belong exclusively to the shared contract; project records cannot
override them. The language-tooling section reports its mechanism from
`facts.editor_protocol`, including LSP, BSP, native build imports, and prepared
dependency environments. Setup instructions are injected into that shared section;
protocol differences do not create page-specific sections or headings. Every
modeled purifier automatically gets feature-matrix navigation on its main page,
full guide, and matrix, using the shared repository-to-matrix registry.

Full guides use `guide-contract.json` for their section vocabulary and order.
Every `guides/*.json` plan assigns each reviewed source section to exactly one
shared section, or records why a shared section is omitted. New source headings
fail validation until their placement is reviewed. The generated
`guide-structure.json` records those choices alongside each guide. Native
explanations remain detailed, but the guide's introduction, contents list,
navigation, and organization are shared. Exact copies of the overview's initial
command sequence are removed from the guide's setup section. Original fragment
identifiers remain usable after reorganization.

Combined native sections can be partitioned with explicit source-block selections
(`heading` and zero-based `blocks`), including `@introduction` for unheaded
README content. Fenced examples remain whole blocks. Every source block must
be placed exactly once; missing, overlapping, or newly added blocks fail
validation. This keeps language tooling and platform limitations in their shared
sections even when a native README combines those topics.

The family export also checks homepage coverage. Adding a purifier homepage link
without its structured record fails CI and publication. Stage the reviewed model
and guide before publishing a new project's site; use `--model --source-status .`
and pin the shared source that includes that review. The family repository must
use GitHub Actions publishing, so raw branch builds cannot overwrite the
generated site.

`docs-site/profiles/locked-wrapper.nix` shares section selections with overridable
Nix module defaults. Profiles do not assume behavioral facts. Shared templates
have fact requirements: the pin-preserving development loop cannot be used
when `facts.relock` is unknown or says `re-resolves`.
The alternative `fresh` workflow template requires `re-resolves`. Select it
with `sections.workflow.template = "fresh"` when that matches the facts;
its wording remains shared across projects with the same behavior.
Command examples use `{commands.lock}`, `{commands.build}`, and related tokens
from the actual invocation recipes; changing a task in the model changes both
the harness invocation and the generated example.

Shared templates can be ordered, named blocks rather than one string. Each
block has `id` and `text`, with optional `when` fact-value conditions and
`whenKnown` prerequisites. Values and command recipes are injected through
the existing `{facts.name}` and `{commands.name}` tokens. Unknown facts do
not satisfy conditions. Fact definitions with `matrix = false` supply
operational or documentation values without becoming feature-matrix rows.

Prefer `extra-explanation` for the remaining project-specific prose:

```nix
sections.offline.blocks.roots.extra-explanation = ''
  Additional instructions specific to this integration.
'';
```

Each block also accepts `before` and `after` prose as escape hatches. The
rendering order is before, shared block content, extra explanation, after.
These slots can be attached to any named block within a section; they do not
create example sections. Unknown block names, misspelled slots, and prose
attached to an inactive conditional block fail validation. The older
section-level `details` field remains supported for compatibility.

To replace or omit a whole section, record why:

```nix
sections.workflow = {
  mode = "replace";
  template = lib.mkForce null;
  details = lib.mkForce "Relocking resolves dependencies again.";
  reason = "This integration does not preserve existing pins.";
};
sections.editor = {
  mode = "omit";
  template = lib.mkForce null;
  details = lib.mkForce null;
  blocks = lib.mkForce {};
  reason = "This tool has no editor integration.";
};
```

Changing copy does not change a behavioral fact; declare both when behavior
differs. All sections must be present, including explicitly omitted sections.
Unknown sections, facts, enum values, and shared template names fail validation.
Avoid copying shared text into `details`; update the shared template or
introduce a named variant with its own applicability conditions.

### Generate and validate

From this repository:

```sh
nix eval --json '.#tests'
python3 -m unittest discover -s docs-site -v
python3 docs-site/export.py --check
python3 docs-site/build.py --output .catalog-source
jekyll build --source .catalog-source --destination .catalog-site
```

The output preserves the existing family homepage and includes project pages,
`catalog.json`, per-project `system.json`, and `content-variations.json`.
Each modeled project page has a subdued footer link to its generated feature
matrix, with declared behavior and explicit unknowns, and to the retained
native reference guide. The family homepage remains the entry point.
The audit records local additions, replacements, omissions, and unresolved
facts. CI runs the model tests, renderer/integration tests, and Jekyll build,
and uploads the resulting reference as an artifact.

To add a project, create `model/projects/<name>.nix` and
`docs-site/projects/<name>.nix`; modules are discovered by filename. Data can
live in typed Nix modules or JSON records under the corresponding `records/`
directories. `model/from-record.nix` gives unestablished capabilities an explicit
unknown state and applies the same Nix option validation.
Do not infer support from a sibling project.

### Adopt in an independent project Pages workflow

The bundled export allows Pages builders to use Python alone:

```sh
python3 .pages-theme/docs-site/prepare.py --repository "$GITHUB_REPOSITORY" \
  --model --source-status .
```

`--model` uses `docs-site/catalog.json`, generated with `export.py`. CI checks
that it agrees with the Nix source model. `--source-status` selects an exact
reviewed variant when available, otherwise builds the canonical bundled model
and guide together. The shared library similarly uses its bundled README and
library scope. Source links identify the documented revision. Native source
changes do not require a coordinated central-site update to pass PR or main
Pages builds, and do not automatically change documented capabilities.

The generated `source-review.json` reports `matched` or `update-needed`, the
documented revision, and changed files. This is a maintenance report, not a
build failure. Invalid models, missing guides and ambiguous or mismatched
review records still fail. Each consumer pins the exact shared documentation
commit; fork PRs need no write token or central-site mutation.

For an explicit strict maintainer audit, use `--model --check-source .` instead.
It compares tracked source and CI configuration with the reviewed fingerprints
and rejects changes, removals or new implementation files. This strict command
is separate from normal documentation build validity.

`robots.txt` comes from the shared repository and permits all crawling. It is
copied into the family site and independent project outputs.

Evaluate the shared model once, then pass its export to the existing preparer:

```sh
nix eval --json '.#documentation' > /tmp/purifier-documentation.json
python3 docs-site/prepare.py --repository nix-purifiers/ant-purifier \
  --catalog /tmp/purifier-documentation.json --output /tmp/pages-source
```

This selects the project record and renders it with the same contract used
for the combined reference. Consumers should pin this repository's commit,
including the model and its lockfile. A pre-evaluated export also works without
Nix on the rendering host. `build.py --export FILE` uses that export directly.

Projects can alternatively provide `docs-site/page.json` beside their README
or use `--content FILE` for a record conforming to the shared contract.
With neither a catalog nor a project record, the preparer retains the existing
README path.

## Reviewed source variants

Reviewed PR source variants can render independently of the main catalog.
Store each under `docs-site/reviews/<repository-name>/<review-id>/`:

- `source.json`: the same repository, revision and file-fingerprint record
  used by `model/repositories.json`.
- `page.json`: the validated Nix documentation export for that reviewed
  source, with matching `repository` and `reviewedRevision`.
- `reference.md`: its reviewed full guide source.
- `guide.json`, when its source sections differ from main: an explicit
  full-guide plan using the same shared guide contract.

`prepare.py --model --check-source <checkout>` first checks the canonical
source, then selects a unique matching reviewed variant. It uses that
variant's model and guide together, and links source files to its reviewed
revision. Unknown source, mismatched model revisions, missing guides and
ambiguous reviews fail. Variants do not alter the canonical catalog or the
combined main site; promoting merged behavior remains an explicit model update.

## Existing README preparation

`prepare.py` turns a purifier's README into Jekyll source using the shared
layout and stylesheet here. Each project pins this repository's commit in
its Pages workflow so theme updates remain reviewable and reproducible.

```sh
python3 docs-site/prepare.py --repository nix-purifiers/lein-purifier \
  --readme /path/to/lein-purifier/README.md --output /tmp/pages-source
jekyll build --source /tmp/pages-source --destination /tmp/pages-site
```

Generated pages embed the family homepage's theme, plus documentation styles,
so they retain the same colors, fonts, column width, and light/dark behavior
when opened locally as well as when hosted. Navigation
links keep the same font metrics during hover, focus and activation.
Source-file links in the README become GitHub links; headings and external
links keep their original destinations.

sbt's release workflow merges these documentation files with its Maven
repository before deploying one combined Pages artifact. Never deploy a
documentation-only artifact over sbt's published packages.

Code examples use source line breaks where possible and visual wrapping on
narrow screens. `docs.js` adds copy buttons that copy the underlying text,
including shell continuations. If clipboard access is denied, it selects
the example for manual copying. Code remains readable with JavaScript off.

## Compatibility evidence and drift

`model/compatibility-tests.json` is the source of tested combinations for both
the Nix model and generated catalog. Each point records exact component roles,
versions, platform, operations, immutable test definitions and successful CI
jobs. These are historical observations at the linked revisions, not inferred
version intervals or a claim that a new default has passed the same tests.
The existing packaged-default inventory is separate.

When a compatibility PR merges, review its native test definitions and actual
CI job results before adding points. Record the exact tested source revision,
all tracked input fingerprints, CI revision and attempt, and scoped job IDs.
A merged source revision may stand for the CI revision only when their complete
input manifests match. Otherwise retain the exact tested source and explain
the difference from the merged revision. Fingerprint every tracked input,
including documentation, structured behavior
models, SDK definitions, lockfiles, fixtures, attributes and all workflows. A
file extension or directory name does not prove that a native build ignores it.
Add the exact operations and
limitations the test establishes. A canceled job, a source-only recipe, an
unmerged PR, or a projection-format test cannot establish SDK compatibility.

Run `python3 docs-site/export.py` after editing the registry. Export validation
rejects missing bindings, changed evidence, mismatched platforms, and catalog
points that differ from the registry. Review the generated catalog diff.

For an explicit Nix scope selection, use `kind: "nix-scope"` and list the actual
attribute names in `inputs`. The renderer labels these as **Nix scope
configuration**; it does not interpret them as project files, environment
variables or command options. Keep the immutable API evidence and tested tuple
separate from packaged defaults, compiler target flags and inferred ranges.

```sh
python3 tools/audit-compatibility-evidence.py
python3 tools/audit-compatibility-evidence.py --fetch --verify-ci \
  --output compatibility-audit.json
```

The first command checks the committed catalog and registry without network
access. The second reads public default branches in temporary bare clones,
rechecks actual GitHub CI jobs and their source inputs, and compares current
tracked inputs with every recorded review. It requires Git and an
authenticated `gh`. A scheduled read-only workflow retains the JSON report and
fails on source drift or unverifiable evidence. It does not change branches,
pins, registry entries, or publication state, and does not execute native tests.

`inputs-match` only means the reviewed inputs have not changed.
`review-needed` preserves the historical observation but requires a maintainer
to rerun or review the affected combinations before claiming current coverage.
Changes to an older point remain visible even when another point has newer
passing evidence. Never update a source fingerprint merely to silence drift.
