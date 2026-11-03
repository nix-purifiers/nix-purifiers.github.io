# Project documentation sites

## Structured behavior model

The behavior catalog lives in `model/projects/*.nix`. It uses typed Nix
modules, with a locked dependency on `nixpkgs.lib` alone. Jekyll remains
the final Markdown renderer. The model is independent of Jekyll and exports
ordinary JSON for other tools.

Each project explicitly records inputs, lockfiles, integration, relocking,
missing/stale-lock behavior, native build and editor commands, platforms,
dependency sources, CLI authentication, offline scope, builder isolation,
and outputs. Known values require source references. Use commit-specific
source links so a claim remains reviewable when the implementation changes.
Sources establish what was reviewed; they are not an automatic proof that
the implementation conforms. Add references to implementation tests as those
claims gain executable checks.

Every field must be addressed. `unknown` and `not-applicable` require a
reason and cannot carry a value. Do not substitute `false`, an empty list,
or an inherited family default for an uninvestigated capability.

```nix
facts.relock = {
  state = "known";
  value = "preserves-pins";
  sources = [ "https://github.com/OWNER/REPO/blob/COMMIT/README.md#workflow" ];
};
facts.credentials = {
  state = "unknown";
  reason = "CLI authentication has not been investigated.";
};
```

The vocabulary, types, section order, shared text, and template applicability
conditions are defined once in `contract.json`. `model/schema.nix` derives
the Nix option types from that contract. The renderer independently validates
exports at the JSON boundary.

`model/profiles/locked-wrapper.nix` shares section selections with overridable
Nix module defaults. Profiles do not assume behavioral facts. Shared templates
have fact requirements: the pin-preserving development loop cannot be used
when `facts.relock` is unknown or says `re-resolves`.
The alternative `fresh` workflow template requires `re-resolves`. Select it
with `sections.workflow.template = "fresh"` when that matches the facts;
its wording remains shared across projects with the same behavior.

Use `sections.<name>.details` to add project-specific instructions below
shared prose. To replace or omit a section, record why:

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
python3 docs-site/build.py --output .catalog-source
jekyll build --source .catalog-source --destination .catalog-site
```

The output includes standard project pages, a comparison table,
`catalog.json`, per-project `system.json`, and `content-variations.json`.
The audit records local additions, replacements, omissions, and unresolved
facts. CI runs the model tests, renderer/integration tests, and Jekyll build,
and uploads the resulting reference as an artifact.

The initial catalog covers Ant and Docker, whose wrapper/plugin and sandbox/VM
differences exercise the model. To add a project, create its Nix module and add
its name to `model/default.nix`. Do not infer support from a sibling project.

### Adopt in an independent project Pages workflow

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
README path. Migration is explicit; this change does not replace all project
sites or their package publication workflows.

## Existing README preparation

`prepare.py` turns a purifier's README into Jekyll source using the shared
layout and stylesheet here. Each project pins this repository's commit in
its Pages workflow so theme updates remain reviewable and reproducible.

```sh
python3 docs-site/prepare.py --repository nix-purifiers/lein-purifier \
  --readme /path/to/lein-purifier/README.md --output /tmp/pages-source
jekyll build --source /tmp/pages-source --destination /tmp/pages-site
```

The theme follows the operating system's light/dark preference. Navigation
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
