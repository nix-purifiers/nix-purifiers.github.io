{ lib, ... }: {
  # Profiles share presentation decisions, never unverified behavioral facts.
  sections = {
    quickstart.template = lib.mkDefault "native";
    workflow.template = lib.mkDefault "locked";
    integration.template = lib.mkDefault "wrapper";
    offline.template = lib.mkDefault "scoped";
    editor.template = lib.mkDefault "command";
    nix_builds.template = lib.mkDefault "builder";
    projections.template = lib.mkDefault "directional";
    scope.template = lib.mkDefault "platforms";
    credits.template = lib.mkDefault "cargo";
  };
}
