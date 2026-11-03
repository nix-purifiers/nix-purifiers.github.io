{ ... }:
let
  source = "https://github.com/nix-purifiers/ant-purifier/blob/793373015c1a35f49877d222939b771b1e52aa9b/README.md";
  known = anchor: value: { state = "known"; inherit value; sources = [ "${source}#${anchor}" ]; };
in {
  imports = [ ../operations/ant.nix ];
  repository = "nix-purifiers/ant-purifier";
  facts = {
    tool = known "quickstart" "Ant and Apache Ivy";
    inputs = known "quickstart" [ "build.xml" "ivy.xml" ];
    lockfiles = known "quickstart" [ "ivy.lock.xml" "ant-purifier.lock.json" ];
    integration = known "native-ant-plugin" "wrapper-and-plugin";
    relock = known "quickstart" "preserves-pins";
    missing_lock = known "quickstart" "warn-and-native";
    stale_lock = known "quickstart" "fail-with-repair";
    editor = known "editor" "jdtls";
    platforms = known "supported-scope" [ "x86_64-linux" "aarch64-linux" ];
    dependency_sources = known "supported-scope" [ "HTTP(S)" ];
    credentials = { state = "unknown"; reason = "README describes fetcher overrides for private mirrors, but does not establish CLI authentication support."; };
    offline_scope = known "supported-scope" "locked-dependencies";
    offline_limits = known "supported-scope" [ "Arbitrary downloads performed by other Ant tasks" ];
    nix_builder = known "nix-builds" "pkgs.ant-purifier.buildAntProject";
    build_isolation = known "nix-builds" "nix-sandbox";
    build_outputs = known "nix-builds" [ "packages" "tests" "release" "fetches" ];
  };
}
