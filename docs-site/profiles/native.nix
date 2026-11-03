{ lib, ... }: {
  sections = {
    quickstart.template = lib.mkDefault "reviewed";
    workflow.template = lib.mkDefault "native";
    integration.template = lib.mkDefault "native";
    offline.template = lib.mkDefault "native";
    editor.template = lib.mkDefault "native";
    nix_builds.template = lib.mkDefault "native";
    projections.template = lib.mkDefault "directional";
    scope.template = lib.mkDefault "native";
    credits.template = lib.mkDefault "cargo";
  };
}
