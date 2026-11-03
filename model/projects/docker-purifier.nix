{ ... }:
let
  known = value: { state = "known"; inherit value; };
in {
  imports = [ ../operations/docker.nix ];
  reviewedRevision = "186edeb4dd1bb0c9806485368b64cd5c1433fac3";
  repository = "nix-purifiers/docker-purifier";
  facts = {
    platform_notes = { state = "not-applicable"; reason = "This integration declares Linux targets only."; };
    editor_protocol = known "lsp";
    editor_supported = known true;
    projection_incoming = known "unsupported";
    projection_incoming_formats = { state = "not-applicable"; reason = "No incoming projection interface is implemented."; };
    projection_incoming_interfaces = { state = "not-applicable"; reason = "No incoming projection interface is implemented."; };
    projection_incoming_limits = known [ "The builder has no projectDependencies or native projection input interface" ];
    projection_outgoing = known "unsupported";
    projection_outgoing_formats = { state = "not-applicable"; reason = "No outgoing projection interface is implemented."; };
    projection_outgoing_interfaces = { state = "not-applicable"; reason = "No outgoing projection interface is implemented."; };
    projection_outgoing_limits = known [ "packages.image exposes a native OCI layout; no projections interface is exported" ];
    prefetch_components = known [ "image layouts" "Docker client" "Buildx" "resolver" "editor worker" ];
    unsupported_features = known [ "remote ADD" "external syntax frontends" "ONBUILD triggers" "dynamic FROM" "explicit FROM --platform" "RUN mounts and heredocs" "foreign layers" "Compose and Bake builds" "cross-platform host builds" "remote build contexts" ];
    wrapper_required = known true;
    native_plugin_coordinate = { state = "not-applicable"; reason = "This integration does not publish a native plugin."; };
    native_plugin_repository = { state = "not-applicable"; reason = "This integration does not publish a native plugin."; };
    native_plugin_bootstrap = { state = "not-applicable"; reason = "This integration does not publish a native plugin."; };
    named_update_example = known "quay.io/prometheus/busybox:latest";
    supported_native_commands = known [ "native-platform, local-context docker build" "docker buildx build" ];
    build_engine = known "Buildah";
    builder_options = known [ "lockFile" "dockerfile" "fetchers" "srcFilter" "buildArgs" "testCommand" ];
    editor_metadata_format = known "none";
    lock_identity = known "oci-sha256";
    tested_toolchain = { state = "unknown"; reason = "Exact tested client and Buildx versions are not recorded in this model."; };
    native_plugin_java_target = { state = "not-applicable"; reason = "This integration does not publish a native plugin."; };
    updates_ignore_file = known true;
    generated_cache_directory = known ".docker-purifier";
    runtime_requirements = known [ "a running Docker daemon" "Buildx with named-context support" ];
    editor_diagnostics = known true;
    editor_navigation = known true;
    editor_completion = { state = "unknown"; reason = "Completion has not been verified through this project integration."; };
    editor_offline = known true;
    editor_dependency_sources = { state = "not-applicable"; reason = "Dockerfile editing does not resolve source libraries from locked base images."; };
    tool = known "Docker";
    inputs = known [ "Dockerfile" ];
    lockfiles = known [ "docker-purifier.lock.json" ];
    integration = known "wrapper";
    relock = known "preserves-pins";
    missing_lock = known "warn-and-native";
    stale_lock = known "fail-with-repair";
    platforms = known [ "x86_64-linux" "aarch64-linux" ];
    dependency_sources = known [ "Public OCI/Docker v2 registries" ];
    credentials = known "anonymous-only";
    offline_scope = known "locked-dependencies";
    offline_limits = known [ "Downloads inside Dockerfile RUN commands" ];
    nix_builder = known "pkgs.docker-purifier.buildDockerProject";
    build_isolation = known "networkless-vm";
    build_outputs = known [ "packages.image" "tests" "release" "fetches" ];
  };
}
