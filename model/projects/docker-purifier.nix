{ ... }:
let
  source = "https://github.com/nix-purifiers/docker-purifier/blob/186edeb4dd1bb0c9806485368b64cd5c1433fac3/README.md";
  known = anchor: value: { state = "known"; inherit value; sources = [ "${source}#${anchor}" ]; };
in {
  imports = [ ../operations/docker.nix ];
  repository = "nix-purifiers/docker-purifier";
  facts = {
    tool = known "quickstart" "Docker";
    inputs = known "quickstart" [ "Dockerfile" ];
    lockfiles = known "quickstart" [ "docker-purifier.lock.json" ];
    integration = known "quickstart" "wrapper";
    relock = known "development-loop" "preserves-pins";
    missing_lock = known "quickstart" "warn-and-native";
    stale_lock = known "quickstart" "fail-with-repair";
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
}
