{ ... }:
let
  source = "https://github.com/nix-purifiers/docker-purifier/blob/186edeb4dd1bb0c9806485368b64cd5c1433fac3/README.md";
  known = anchor: value: { state = "known"; inherit value; sources = [ "${source}#${anchor}" ]; };
in {
  imports = [ ../profiles/locked-wrapper.nix ];
  repository = "nix-purifiers/docker-purifier";
  summary = "Locked, Nix-resolved base images for Docker builds.";
  facts = {
    tool = known "quickstart" "Docker";
    inputs = known "quickstart" [ "Dockerfile" ];
    lockfiles = known "quickstart" [ "docker-purifier.lock.json" ];
    integration = known "quickstart" "wrapper";
    relock = known "development-loop" "preserves-pins";
    missing_lock = known "quickstart" "warn-and-native";
    stale_lock = known "quickstart" "fail-with-repair";
    native_build = known "quickstart" "docker build -t my-app .";
    editor = known "editor" "docker-langserver --stdio";
    platforms = known "supported-language-repositories" [ "x86_64-linux" "aarch64-linux" ];
    dependency_sources = known "supported-language-repositories" [ "Public OCI/Docker v2 registries" ];
    credentials = known "supported-language-repositories" "anonymous-only";
    offline_scope = known "working-offline" "locked-dependencies";
    offline_limits = known "working-offline" [ "Downloads inside Dockerfile RUN commands" ];
    nix_builder = known "optional-nix-build" "pkgs.docker-purifier.buildDockerProject";
    build_isolation = known "optional-nix-build" "networkless-vm";
    build_outputs = known "optional-nix-build" [ "packages.image" "tests" "release" "fetches" ];
  };
  sections = {
    quickstart.details = ''
      Start Docker before running these commands. Also commit the updated Docker
      ignore file: locking excludes `.docker-purifier` from the build context.
      Run the image with `docker run --rm my-app`.
    '';
    workflow.details = ''
      A named update selects a literal image reference, for example
      `docker-purifier update quay.io/prometheus/busybox:latest`.
      OCI manifest, configuration, and layer coordinates retain their native
      SHA-256 digests. The lock adds platforms and input fingerprints.
    '';
    integration.details = ''
      The wrapper is required for native builds. An existing Docker daemon and
      Buildx with named-context support are required. Only native-platform,
      local-context `docker build` and `docker buildx build` are wrapped;
      other Docker commands run normally.
    '';
    offline.details = ''
      Prefetch roots image layouts, Docker client, Buildx, resolver, and editor
      worker beside the selected lock. Host RUN commands retain network access;
      vendor their inputs or prepare caches before using `docker build --network=none`.
    '';
    editor.details = ''
      Syntax, completion, and stage-definition support work without registry access.
    '';
    nix_builds.details = ''
      The builder uses native Buildah in a networkless software VM, requiring
      neither host root privileges nor KVM. Software emulation adds overhead.
      Use the pinned nixpkgs or a compatible `vmTools` interface.
      See [builder configuration](${source}#optional-nix-build).
    '';
    scope.details = ''
      The default CLI supports anonymous registries; builder fetcher overrides
      can integrate corporate transport. Remote ADD, external syntax frontends,
      ONBUILD triggers, dynamic FROM, explicit FROM --platform, RUN mounts/heredocs,
      foreign layers, and Compose/Bake builds are not yet supported.
      Cross-platform host builds and remote contexts are also unsupported.
      See [troubleshooting and external locks](${source}#troubleshooting).
    '';
  };
}
