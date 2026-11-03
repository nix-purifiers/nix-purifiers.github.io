{ ... }:
let
  known = value: { state = "known"; inherit value; };
in {
  imports = [ ../operations/ant.nix ];
  repository = "nix-purifiers/ant-purifier";
  facts = {
    tool = known "Ant and Apache Ivy";
    inputs = known [ "build.xml" "ivy.xml" ];
    lockfiles = known [ "ivy.lock.xml" "ant-purifier.lock.json" ];
    integration = known "wrapper-and-plugin";
    relock = known "preserves-pins";
    missing_lock = known "warn-and-native";
    stale_lock = known "fail-with-repair";
    editor = known "jdtls";
    platforms = known [ "x86_64-linux" "aarch64-linux" ];
    dependency_sources = known [ "HTTP(S)" ];
    credentials = { state = "unknown"; reason = "README describes fetcher overrides for private mirrors, but does not establish CLI authentication support."; };
    offline_scope = known "locked-dependencies";
    offline_limits = known [ "Arbitrary downloads performed by other Ant tasks" ];
    nix_builder = known "pkgs.ant-purifier.buildAntProject";
    build_isolation = known "nix-sandbox";
    build_outputs = known [ "packages" "tests" "release" "fetches" ];
  };
}
