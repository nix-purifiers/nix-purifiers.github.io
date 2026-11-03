{ lib, ... }:
let
  inherit (lib) mkOption types;
  text = types.addCheck types.str (s: s != "");
  binding = types.addCheck (types.attrsOf text) (x: builtins.attrNames x == [ "binding" ]);
  expression = types.addCheck (types.attrsOf text) (x:
    builtins.attrNames x == [ "binding" ] || x == { splice = "arguments"; });
  operation = types.submodule {
    options = {
      state = mkOption { type = types.enum [ "available" "unsupported" "unknown" ]; default = "available"; };
      capability = mkOption { type = types.nullOr text; default = null; };
      arguments = mkOption { type = types.listOf (types.either text expression); default = []; };
      environment = mkOption { type = types.attrsOf (types.oneOf [ text binding ]); default = {}; };
      directory = mkOption { type = binding; default = { binding = "project_root"; }; };
      reason = mkOption { type = types.nullOr text; default = null; };
      sources = mkOption { type = types.listOf text; default = []; };
      minimumArguments = mkOption { type = types.ints.unsigned; default = 0; };
    };
  };
in {
  options.operations = mkOption {
    type = types.attrsOf operation;
    default = {};
    apply = operations: lib.mapAttrs (name: op:
      if op.state == "available" then
        if op.capability == null || op.reason != null || op.sources == [] then
          throw "${name}: available operations require a capability and sources, without an uncertainty reason"
        else if builtins.length (builtins.filter (x: builtins.isAttrs x && x ? splice) op.arguments) > 1 then
          throw "${name}: arguments may be spliced at most once"
        else if op.minimumArguments > 0 && !(builtins.elem { splice = "arguments"; } op.arguments) then
          throw "${name}: required arguments need an argument splice"
        else op
      else if op.reason == null || op.capability != null || op.arguments != []
        || op.environment != {} || op.sources != [] then
        throw "${name}: unsupported/unknown operations require a reason and no executable recipe"
      else op
    ) operations;
  };
}
