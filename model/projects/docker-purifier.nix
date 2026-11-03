{ ... }:
let
  known = value: { state = "known"; inherit value; };
in {
  imports = [ ../operations/docker.nix ];
  repository = "nix-purifiers/docker-purifier";
  facts = {
    tool = known "Docker";
    inputs = known [ "Dockerfile" ];
    lockfiles = known [ "docker-purifier.lock.json" ];
    integration = known "wrapper";
    relock = known "preserves-pins";
    missing_lock = known "warn-and-native";
    stale_lock = known "fail-with-repair";
    editor = known "docker-langserver --stdio";
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
