{ ... }:
let
  known = value: { state = "known"; inherit value; };
in {
  imports = [ ../operations/ant.nix ];
  repository = "nix-purifiers/ant-purifier";
  facts = {
    projection_incoming = known "conditional";
    projection_incoming_formats = known [ "Maven" ];
    projection_incoming_interfaces = known [ "projectDependencies" "--input" "lockfile.projectInputs" ];
    projection_incoming_limits = known [ "The Nix input path requires the producer's projections.maven view; an Ivy-only projection is not accepted" "Keep dependency declarations in ivy.xml; the supplied catalog selects immutable Nix-derived versions" ];
    projection_outgoing = known "conditional";
    projection_outgoing_formats = known [ "Maven" "Ivy" ];
    projection_outgoing_interfaces = known [ "projections.maven" "projections.ivy" ];
    projection_outgoing_limits = known [ "Set publishTarget to expose project publications" "Original Maven POM metadata, including parent and BOM closure, is required; Ivy-only dependency graphs fail projection evaluation" ];
    prefetch_components = known [ "dependency repository" "compiler" "Ant" "plugin" "editor toolchain" ];
    unsupported_features = known [ "inline Ivy resolution" "inherited descriptors" "branches" "multiple project base directories" "custom cache managers" "explicit artifact URLs" ];
    wrapper_required = known false;
    native_plugin_coordinate = known "io.github.nix-purifiers:ant-purifier";
    native_plugin_repository = known "https://nix-purifiers.github.io/ant-purifier/maven/";
    native_plugin_bootstrap = known "maven-impure";
    named_update_example = known "commons-lang3";
    supported_native_commands = known [ "Ant targets" ];
    build_engine = known "Ant";
    builder_options = known [ "buildTargets" "publishTarget" "lockFile" "ivyLock" "ivyFile" "buildFile" "fetchers" "projectDependencies" ];
    editor_metadata_format = known "eclipse";
    lock_identity = known "ivy-revisions";
    tested_toolchain = known [ "Ant 1.10.18" "Ivy 2.6.0" "JDK 21" ];
    native_plugin_java_target = known "11";
    updates_ignore_file = known false;
    generated_cache_directory = known ".ant-purifier";
    runtime_requirements = { state = "not-applicable"; reason = "No additional native prerequisites are declared."; };
    editor_diagnostics = known true;
    editor_navigation = known true;
    editor_completion = { state = "unknown"; reason = "Completion has not been verified through this project integration."; };
    editor_offline = known true;
    editor_dependency_sources = known true;
    tool = known "Ant and Apache Ivy";
    inputs = known [ "build.xml" "ivy.xml" ];
    lockfiles = known [ "ivy.lock.xml" "ant-purifier.lock.json" ];
    integration = known "wrapper-and-plugin";
    relock = known "preserves-pins";
    missing_lock = known "warn-and-native";
    stale_lock = known "fail-with-repair";
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
