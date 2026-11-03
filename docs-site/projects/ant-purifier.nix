{ ... }:
let
  source = "https://github.com/nix-purifiers/ant-purifier/blob/793373015c1a35f49877d222939b771b1e52aa9b/README.md";
in {
  imports = [ ../../model/projects/ant-purifier.nix ../profiles/locked-wrapper.nix ];
  summary = "Locked, Nix-resolved dependencies for Ant and Apache Ivy.";
  sections = {
    quickstart.blocks.commands.extra-explanation = ''
      The project needs an Ivy resolution target. The default is `resolve`;
      select another with `ant-purifier --resolve-target dependencies lock`.
      Use `--property name=value` for resolver properties.
    '';
    integration.blocks.native-plugin.extra-explanation = ''
      See the [activation example](${source}#native-ant-plugin).
    '';
    editor.blocks.metadata.extra-explanation = ''
      Existing IvyDE configuration is preserved for restoration when the lock
      is removed. JDT's workspace stays outside the source tree.
    '';
    nix_builds.blocks.main.extra-explanation = ''
      `packages.project` builds the project. `packages.environment` contains
      the locked repository. `publishTarget` enables native Ivy publications
      through `packages.repository`.
      See [builder examples](${source}#nix-builds).
    '';
  };
}
