{ config, lib, ... }:
let
  inherit (lib) mkOption types;
  defaultsByProject = (builtins.fromJSON (builtins.readFile ./toolchain-defaults.json)).projects;
  requirementsByProject = (builtins.fromJSON (builtins.readFile ./version-requirements.json)).projects;
  requirements = requirementsByProject.${projectName} or {};
  projectName = lib.last (lib.splitString "/" config.repository);
  text = types.addCheck types.str (s: builtins.match ".*[^ \n\t].*" s != null);
  nonempty = type: types.addCheck (types.listOf type) (xs: xs != []);
  revision = types.strMatching "[0-9a-f]{40}";
  roles = [ "purifier-implementation" "native-tool" "native-tool-runtime" "project-runtime" "compiler" "host-helper" "addon-target" "build-target" "native-format" ];
  component = {
    role = mkOption { type = types.enum roles; };
    name = mkOption { type = text; };
    version = mkOption { type = types.strMatching "[0-9A-Za-z][0-9A-Za-z.+_:-]*"; };
  };
  proof = {
    sourceRevision = mkOption { type = revision; };
    evidence = mkOption { type = nonempty (types.strMatching "https://[^ ]+"); };
  };
  point = types.submodule {
    options = proof // {
      id = mkOption { type = text; };
      components = mkOption { type = nonempty (types.submodule { options = component; }); };
      system = mkOption { type = text; };
      operations = mkOption { type = nonempty text; };
      notes = mkOption { type = types.listOf text; default = []; };
    };
  };
in {
  options.compatibility = mkOption {
    default = {};
    type = types.submodule {
      options = {
        defaults = mkOption { default = defaultsByProject.${projectName} or []; type = types.listOf (types.submodule { options = component // proof // {
          selection = mkOption { type = text; default = "default"; };
          systems = mkOption { type = nonempty text; };
        }; }); };
        projectSelections = mkOption {
          default = requirements.projectSelections or [];
          type = types.listOf (types.submodule {
            options = proof // {
              role = component.role;
              name = component.name;
              kind = mkOption { type = types.enum [ "project-file" "environment" "lockfile" "command-option" "nix-scope" ]; };
              inputs = mkOption { type = nonempty text; };
              description = mkOption { type = text; };
            };
          });
        };
        testedPoints = mkOption { default = []; type = types.listOf point; };
        supportedRanges = mkOption {
          default = [];
          type = types.listOf (types.submodule {
            options = proof // {
              role = component.role;
              name = component.name;
              range = mkOption { type = text; };
              systems = mkOption { type = nonempty text; };
              operations = mkOption { type = nonempty text; };
              basis = mkOption { type = text; };
              supportingTests = mkOption { type = nonempty text; };
            };
          });
        };
        limitations = mkOption {
          default = requirements.limitations or [];
          type = types.listOf (types.submodule { options = proof // { text = mkOption { type = text; }; }; });
        };
      };
    };
    apply = value:
      let
        ids = map (p: p.id) value.testedPoints;
        defaultKeys = lib.concatMap (p: map (system: "${p.selection}:${p.role}:${p.name}:${system}") p.systems) value.defaults;
        uniqueComponents = p:
          let keys = map (c: "${c.role}:${c.name}") p.components;
          in builtins.length keys == builtins.length (lib.unique keys);
      in if builtins.length defaultKeys != builtins.length (lib.unique defaultKeys) then
        throw "A packaged selection cannot assert two versions of the same component on one platform"
      else if builtins.length ids != builtins.length (lib.unique ids) then
        throw "Compatibility test IDs must be unique"
      else if !(lib.all uniqueComponents value.testedPoints) then
        throw "A tested combination cannot select two versions of the same component"
      else if !(lib.all (r: lib.all (id: builtins.elem id ids) r.supportingTests) value.supportedRanges) then
        throw "Supported ranges require explicit review and existing supporting tests"
      else value;
  };
}
