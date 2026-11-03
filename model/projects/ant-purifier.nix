{ ... }:
let
  source = "https://github.com/nix-purifiers/ant-purifier/blob/793373015c1a35f49877d222939b771b1e52aa9b/README.md";
  known = anchor: value: { state = "known"; inherit value; sources = [ "${source}#${anchor}" ]; };
in {
  imports = [ ../profiles/locked-wrapper.nix ];
  repository = "nix-purifiers/ant-purifier";
  summary = "Locked, Nix-resolved dependencies for Ant and Apache Ivy.";
  facts = {
    tool = known "quickstart" "Ant and Apache Ivy";
    inputs = known "quickstart" [ "build.xml" "ivy.xml" ];
    lockfiles = known "quickstart" [ "ivy.lock.xml" "ant-purifier.lock.json" ];
    integration = known "native-ant-plugin" "wrapper-and-plugin";
    relock = known "quickstart" "preserves-pins";
    missing_lock = known "quickstart" "warn-and-native";
    stale_lock = known "quickstart" "fail-with-repair";
    native_build = known "quickstart" "ant test";
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
  sections = {
    quickstart.details = ''
      The project needs an Ivy resolution target. The default is `resolve`;
      select another with `ant-purifier --resolve-target dependencies lock`.
      Use `--property name=value` for resolver properties.
      The native lock records revisions; the companion records artifact hashes,
      original metadata, and resolution configuration.
    '';
    workflow.details = ''
      `ant-purifier update commons-lang3` updates a named dependency while
      retaining the other selected revisions.
    '';
    integration.details = ''
      Alternatively, activate the native Ant plugin in the build. It is
      published at `https://nix-purifiers.github.io/ant-purifier/maven/` as
      `io.github.nix-purifiers:ant-purifier`. Keep its bootstrap classpath
      separate from application dependencies. Native Maven bootstrap resolution
      is impure; use the wrapper for pure plugin resolution.
      See the [activation example](${source}#native-ant-plugin).
    '';
    offline.details = ''
      Prefetch roots the dependency repository, compiler, Ant, plugin, and editor
      toolchain beside the selected lockfile.
    '';
    editor.details = ''
      The launcher prepares Eclipse metadata with immutable dependency and source
      JAR paths and preserves IvyDE configuration for restoration when the lock
      is removed. JDT's workspace stays outside the source tree.
    '';
    nix_builds.details = ''
      `packages.project` builds in the sandbox. `packages.environment` contains
      the locked repository. `publishTarget` enables native Ivy publications
      through `packages.repository`. Maven projection requires original POM
      metadata, including parent and BOM closure.
      See [builder options and examples](${source}#nix-builds).
    '';
    scope.details = ''
      Checked with Ant 1.10.18, Ivy 2.6.0, and JDK 21; the plugin targets Java 11.
      Inline resolution, inherited descriptors, branches, multiple project base
      directories, custom cache managers, and explicit artifact URLs are rejected.
      Native Nix project dependency inputs are not yet supported.
    '';
  };
}
