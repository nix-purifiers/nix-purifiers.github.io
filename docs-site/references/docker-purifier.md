# docker-purifier

Locked, Nix-resolved base images for Docker builds.

## Quickstart

In your existing project, with Docker running:

```sh
nix shell 'github:nix-purifiers/docker-purifier'
docker-purifier lock
docker-purifier prefetch
docker build -t my-app .
docker run --rm my-app
```

Commit `docker-purifier.lock.json` and the updated Docker ignore file. The
wrapper supplies local OCI layouts for locked `FROM` and external
`COPY --from` images. Docker builds the project on your daemon.

The supplied wrapper is required. You can install it through your normal
Nix configuration. Without an applicable lock it warns and runs ordinary,
impure Docker, preserving arguments, streams and exit status. Invalid or
stale build locks fail with a repair command.

## Development loop

After changing the Dockerfile or its ignore rules:

```sh
docker-purifier lock
docker-purifier prefetch
docker build -t my-app .
```

`lock` retains image digests even when upstream tags move. Repeating it
without changes produces the same lock bytes. To update all references:

```sh
docker-purifier update
docker-purifier prefetch
```

A named update changes only that literal reference:

```sh
docker-purifier update quay.io/prometheus/busybox:latest
```

Native OCI manifests, configuration and layer digests remain SHA-256
coordinates. The lock adds platform selections and input fingerprints;
it does not replace OCI digests with a repacked archive hash.

## Working offline

```sh
docker-purifier prefetch
docker build -t my-app .
```

Prefetch keeps the image layouts, Docker client, Buildx, resolver and editor
worker alive through garbage-collector roots beside the selected lock.
Base images come from the local Nix cache. Commands inside `RUN` retain normal
network access; downloads by tools such as uv are outside this image lock.
For an offline build, vendor those inputs or supply a prepared package cache:

```sh
docker build --network=none -t my-app .
```

`lock` excludes `.docker-purifier` from the active Docker ignore file, so
the generated cache does not enter images through `COPY .`.

An existing Docker daemon and Buildx with named-context support are
required. The default Docker driver loads verified Nix-built image archives;
other drivers use local OCI contexts. The shell supplies compatible client and Buildx packages. Docker
connection options and explicit builder selection remain native options.
The wrapper supports native-platform, local-context `docker build` and
`docker buildx build` commands. Other Docker commands run normally.

## Editor

Run `docker-langserver --stdio` from the same shell. Its syntax, completion
and stage-definition support work without registry access. The sandbox
editor check resolves a `COPY --from` reference to its declared build stage.

## Troubleshooting

- **Dockerfile or ignore rules changed:** run `docker-purifier lock`, then
  `prefetch`.
- **No daemon:** start Docker through your normal system configuration.
- **An image platform is missing:** relock with the intended platforms.
  Linux AMD64 and ARM64 are recorded by default.
- **Dependency metadata is damaged:** `lock` repairs it against a recoverable
  pinned digest; if the digest itself is lost, resolution may need the registry.
- **A Nix sandbox build needs downloads:** vendor those inputs or supply a
  prepared cache. Host builds retain normal network access. Remote `ADD`, external syntax frontends, `ONBUILD` base triggers, dynamic
  `FROM`, explicit `FROM --platform`, `RUN` mounts/heredocs,
  foreign layers, and Compose/Bake builds are not yet supported.

Stage aliases must differ from external image references. Cross-platform
host builds and remote build contexts are not supported yet.

Alternate Dockerfiles and external locks are supported:

```sh
docker-purifier \
  --dockerfile docker/production.Dockerfile \
  --lockfile ../locks/docker.json lock
docker-purifier \
  --dockerfile docker/production.Dockerfile \
  --lockfile ../locks/docker.json prefetch
```

Set `DOCKER_PURIFIER_LOCKFILE` for native build commands using an external
lock. Native `-f` selects the Dockerfile. The working tree does not need Nix
files or a generated development shell.

## Supported language repositories

Public OCI/Docker v2 registries are supported, including anonymous bearer
authentication. Immutable manifests, configuration and layers are verified
against their native digests. Registry tokens do not enter the lock.
The builder accepts `fetchers` overrides for corporate transport integration.
The default CLI transport supports anonymous registries.

The flake targets x86_64 and ARM Linux. No native plugin package repository
is needed; GitHub Pages hosts the documentation.

## Examples

`examples/hello` is a multi-stage build with a locked BusyBox image:

```sh
nix shell 'github:nix-purifiers/docker-purifier'
cd examples/hello
docker-purifier prefetch
docker build -t purifier-hello .
docker run --rm purifier-hello
```

### Optional Nix build

The overlay adds only the `docker-purifier` scope:

```nix
let
  pkgs = import nixpkgs {
    inherit system;
    overlays = [ purifier.overlays.default ];
  };
  project = pkgs.docker-purifier.buildDockerProject {
    src = ./.;
    lockFile = ../locks/docker.json;
    dockerfile = ./Dockerfile;
  };
in {
  packages.default = project.packages.image;
  checks.default = project.tests;
}
```

This builder uses native Buildah inside a networkless software VM. It needs
neither host root privileges nor KVM. Software emulation adds overhead.
Use the pinned nixpkgs or a compatible package set providing the same
`vmTools` interface. The builder supports `fetchers`, `srcFilter`, `buildArgs`,
`testCommand` and scope overrides.

The result exposes `packages.image` (an OCI layout), `tests`, `release` and
`fetches`. `lib.docker-purifier.readLock` reads manifests and blob coordinates during
evaluation without import-from-derivation. The Nix-built release contains deterministic source
and OCI image archives:

```sh
docker-purifier publish \
  --repo OWNER/PROJECT --tag v1.0.0
```

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
