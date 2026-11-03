{ ... }:
let
  known = value: { state = "known"; inherit value; };
in {
  imports = [ ../operations/docker.nix ];
  repository = "nix-purifiers/docker-purifier";
  facts = {
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
