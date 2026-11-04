# Purifier model and harness

The model has three consumers: documentation, the operational harness, and
shared behavioral tests. `model/projects/*.nix` describes a purifier without
requiring a page. Documentation lives separately in `docs-site/projects/`.

## Ownership boundary

The model teaches the harness how to invoke a tool. It records argument
vectors, environment bindings, working directories, argument forwarding,
supported operations, and the behavior those operations promise.

The bespoke integration supplies capabilities. A capability can be an
existing executable or a callable that performs the integration's preparation
and invocation. It owns native details such as installing an sbt plugin,
constructing a repository configuration, selecting the appropriate JDK, or
binding an existing wrapper. The model does not generate those implementations.

For example, `records/sbt-purifier.json` says that `lock` invokes the supplied `sbt`
capability with `-batch`, optional forwarded arguments, then `nixLock`, from
the project root, with `SBT_PURIFIER_LOCKFILE` bound to the selected lockfile.
The provider is responsible for supplying an sbt installation with the purifier
plugin installed. `update` uses `nixLockUpdate` and rejects extra arguments;
named updates are explicitly unsupported. `prefetch` uses the separately
provided `sbt-purifier` capability.

The same mechanism works for Ant and Docker. The executor has no branch
selecting behavior by tool name.

Reviewed revisions and source fingerprints live in `repositories.json`.
They bind the declared capabilities to implementation and CI scope without
using generated prose as supporting evidence. A target system is separate
from a validation guarantee: `platform_notes` records restrictions such as
contributor-only unsandboxed Darwin testing or unsupported downloaded JVMs.
The shared library has its own scope in `library.json`; downstream tools do
not inherit its platform support automatically.

Language server integration (LSP) connects the user's existing editor to the
purified development environment. The model records language-server
diagnostics, completion, definition lookup, locked dependency source retrieval,
and offline use separately from the `editor` launcher recipe. These are server
capabilities; they do not claim end-to-end verification with every editor client.
Native source retrieval may require server-specific client extensions.

Additional editor clients can use the same language-server capability. A new
server or native editor adapter belongs in bespoke integration glue; the model
then records the capabilities it actually provides. Generic editor features
are useful here insofar as they work with the purified project's environment.

Projection support is directional: incoming means consuming other Nix-built
projects through native projections; outgoing means exporting such projections
for consumers. Each direction records support, formats, interfaces, and
limitations separately. Native artifacts alone do not imply a projection
interface. Conditional support records its prerequisites, including differences
between package-level and aggregate outputs. Unsupported directions cannot
advertise formats or interfaces.

## Invocation expressions

`invocations.nix` validates each operation. Arguments are literal strings,
`{ binding = "name"; }` for a runtime value, or one
`{ splice = "arguments"; }` for forwarded arguments. Environment values are
literals or bindings. There is no shell interpolation; a task containing
spaces, quotes, or shell metacharacters remains one argument.

Available operations require a capability. Optional source references can
point to implementation or conformance tests. Unsupported
and unknown operations require a reason and cannot carry an executable recipe.
`minimumArguments` prevents a named update with no names from turning into an
update of everything.

The Python API is in `harness/runtime.py`. `Executable` binds a capability to
an argv prefix and optional environment; a callable instead receives the
resolved `Invocation` and returns a `subprocess.CompletedProcess`. Native
streams are inherited unless the caller requests capture, and the native exit
status is preserved. No executable is guessed when a capability is missing.

These are distinct conditions:

- **Unsupported:** the tool cannot provide the operation.
- **Unknown:** the invocation has not been modeled yet.
- **Capability unavailable:** the model offers it, but this provider has not
  supplied the required implementation.

## Run an operation

Export the behavior catalog independently of the documentation:

```sh
nix eval --json '.#catalog' > /tmp/purifier-model.json
nix eval --json '.#testPlans' > /tmp/purifier-tests.json
```

The bespoke integration supplies a provider, for example:

```json
{
  "capabilities": {
    "sbt": { "command": ["/path/to/existing/purifier-enabled-sbt"] }
  },
  "context": {
    "project_root": "/path/to/project",
    "lockfile": "/path/to/project/sbt-purifier.lock.json"
  }
}
```

```sh
python3 harness/cli.py --catalog /tmp/purifier-model.json \
  --project sbt-purifier --provider /path/to/provider.json lock
```

Python providers can supply more capabilities than this executable-only JSON
interface, including callbacks for fixture control and observations.

## Shared behavioral tests

`test-plan.nix` derives tests from declared behavior and available operations.
`harness/conformance.py` executes those plans with the same runtime and native
invocation recipes used for actual operations.

The shared relock test:

1. Invokes the modeled lock operation.
2. Asks the fixture provider for normalized locked selections.
3. Asks it to make a newer eligible upstream version available.
4. Locks again and compares the selections with the declared retention policy.

The fixture provider implements `locked-selections` and `advance-upstream`.
It owns the native lock format and controlled repository mechanics. The
shared test owns the assertion. An empty dependency selection fails rather
than making pin retention pass vacuously. A modeled native `test` operation
also becomes a shared test case.

Missing capabilities or fixture support produce **blocked** results, never
passed tests. Every fact without a generated test is listed in
`uncoveredFacts`, and a report cannot claim complete coverage while those gaps
remain. The structured model declares the behavior; tests verify it.

The integration test exercises Docker's real CLI and pin-retention algorithm.
Its bespoke fixture adapter supplies controlled registry metadata, so no Docker
daemon or external registry is needed. It also checks that a resolver that
incorrectly advances pins fails the shared test.

```sh
nix eval --json '.#tests'
PURIFIER_DOCKER_SOURCE=/path/to/docker-purifier \
  python3 -m unittest discover -s harness -v
```

CI checks out the reviewed Docker source revision for this test. Without that
source supplied, the Docker integration test is explicitly skipped; it does
not substitute a synthetic resolver and claim the real integration passed.

## Lifecycle and projection coverage

`nix eval --json '.#coveragePlan'` exports obligations separately from the
existing executable `testPlans`. Every modeled project gets explicit dependency
add/drop/bump, native ↔ Nix origin, buildable add/drop, transitive eviction,
multiple-input, outgoing ordinary-consumer, and adopter-sandwich obligations.
Applicability is `required`, `needs-review`, or `not-applicable`; execution starts
at `not-run`. Buildable applicability and native SDK matrices remain review
gaps because the behavior model does not yet specify them.

Projection candidates preserve producer, consumer, format, both interface names,
the intersection of declared systems, and each side's limitations. Equal format
names generate candidates awaiting compatibility review. Cases must cover
purifier → ordinary → purifier and ordinary → purifier → ordinary chains, with
the middle publisher's own direct and transitive conflicts.

`harness/coverage.py` audits individual observations against independently
selected source, SDK, system, cache profile and fixture digests. A runner's
overall success cannot supply missing observations. Stale sources, changed
plans, duplicate contexts, or a cold result substituted for a warm result
remain incomplete. A reviewed SDK matrix additionally requires every declared
system/SDK/cache combination. Fact-to-test coverage from `testPlans` remains
separate: completing an observation does not exhaust every associated fact.

```sh
nix eval --json '.#coveragePlan' > coverage-plan.json
python3 -B harness/coverage.py --plan coverage-plan.json \
  --evidence evidence.json --expected expected-contexts.json > coverage-audit.json
python3 -B docs-site/build.py --coverage-plan coverage-plan.json \
  --coverage-audit coverage-audit.json
```

Expected contexts must be declared from the selected sources and SDKs,
independently of the execution report being audited. Missing projects and
observations stay unrun. The central site publishes `/testing/`, the plan,
per-project JSON and an optional context-bound execution audit. A build without
an audit states that no execution evidence is attached and removes any stale
audit artifact. Evidence from another plan is rejected before publication.

Shared-library source variants use
`docs-site/reviews/purifier/<revision>/{source.json,library.json,reference.md}`.
They retain the library scope model rather than creating a native-tool catalog
page. The model repository and reviewed revision must match the source record;
its platforms, limitations and validation remain explicit string lists. The
reference must be the exact README bytes fingerprinted by that source record.
`prepare.py --model --check-source` selects the paired scope and reference,
pins their source links to the reviewed revision, and emits `library.json`.
Unreviewed changes, multiple matching variants, mismatched models and missing
or unpaired references fail before output. Canonical library rendering retains
its existing model and README behavior.
