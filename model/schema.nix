{ lib, ... }:
let
  inherit (lib) mkOption types;
  text = types.addCheck types.str (s: builtins.match ".*[^ \n\t].*" s != null);
  fact = valueType: mkOption {
    type = types.submodule {
      options = {
        state = mkOption { type = types.enum [ "known" "unknown" "not-applicable" ]; };
        value = mkOption { type = types.nullOr valueType; default = null; };
        sources = mkOption { type = types.listOf text; default = []; };
        reason = mkOption { type = types.nullOr text; default = null; };
      };
    };
    apply = f:
      if f.state == "known" then
        if f.value != null && f.sources != [] && f.reason == null then f
        else throw "Known facts require a value and sources, and cannot have an uncertainty reason"
      else if f.value == null && f.sources == [] && f.reason != null then f
      else throw "Unknown/not-applicable facts require a reason and cannot assert a value or sources";
  };
  strings = types.addCheck (types.listOf text) (xs: xs != []);
  definitions = (builtins.fromJSON (builtins.readFile ./contract.json)).facts;
in {
  imports = [ ./invocations.nix ];
  options = {
    repository = mkOption {
      type = types.addCheck (types.strMatching "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
        (s: !(builtins.elem (lib.last (lib.splitString "/" s)) [ "." ".." ]));
    };
    facts = lib.mapAttrs (_: definition: fact (
      if definition ? enum then types.enum definition.enum
      else if definition.type == "string" then text
      else if definition.type == "strings" then strings
      else throw "Unsupported fact type: ${definition.type}"
    )) definitions;
  };
}
