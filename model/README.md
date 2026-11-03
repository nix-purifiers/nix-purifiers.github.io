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

For example, `operations/sbt.nix` says that `lock` invokes the supplied `sbt`
capability with `-batch`, optional forwarded arguments, then `nixLock`, from
the project root, with `SBT_PURIFIER_LOCKFILE` bound to the selected lockfile.
The provider is responsible for supplying an sbt installation with the purifier
plugin installed. `update` uses `nixLockUpdate` and rejects extra arguments;
named updates are explicitly unsupported. `prefetch` uses the separately
provided `sbt-purifier` capability.

The same mechanism works for Ant and Docker. The executor has no branch
selecting behavior by tool name.

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
