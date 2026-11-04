{ lib, ... }:
let
  inherit (lib) mkOption types;
  text = types.addCheck types.str (s: builtins.match ".*[^ \n\t].*" s != null);
  nonempty = type: types.addCheck (types.listOf type) (xs: xs != []);
  revision = types.strMatching "[0-9a-f]{40}";
  roles = [ "native-tool" "native-tool-runtime" "project-runtime" "compiler" "host-helper" "addon-target" "build-target" "native-format" ];
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
        defaults = mkOption { default = []; type = types.listOf (types.submodule { options = component // proof; }); };
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
          default = [];
          type = types.listOf (types.submodule { options = proof // { text = mkOption { type = text; }; }; });
        };
      };
    };
    apply = value:
      let
        ids = map (p: p.id) value.testedPoints;
        uniqueComponents = p:
          let keys = map (c: "${c.role}:${c.name}") p.components;
          in builtins.length keys == builtins.length (lib.unique keys);
      in if builtins.length ids != builtins.length (lib.unique ids) then
        throw "Compatibility test IDs must be unique"
      else if !(lib.all uniqueComponents value.testedPoints) then
        throw "A tested combination cannot select two versions of the same component"
      else if !(lib.all (r: lib.all (id: builtins.elem id ids) r.supportingTests) value.supportedRanges) then
        throw "Supported ranges require explicit review and existing supporting tests"
      else value;
  };
}
