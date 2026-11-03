{ lib, ... }:
let
  inherit (lib) mkOption types;
  text = types.addCheck types.str (s: builtins.match ".*[^ \n\t].*" s != null);
in {
  options = {
    summary = mkOption { type = text; };
    values = mkOption { type = types.attrsOf types.str; default = {}; };
    sections = mkOption {
      type = types.attrsOf (types.submodule {
        options = {
          mode = mkOption { type = types.enum [ "shared" "replace" "omit" ]; default = "shared"; };
          template = mkOption { type = types.nullOr text; default = null; };
          details = mkOption { type = types.nullOr text; default = null; };
          reason = mkOption { type = types.nullOr text; default = null; };
          title = mkOption { type = types.nullOr text; default = null; };
          blocks = mkOption {
            default = {};
            type = types.attrsOf (types.submodule {
              options = lib.genAttrs [ "extra-explanation" "before" "after" ] (_: mkOption {
                type = types.nullOr text; default = null;
              });
            });
          };
        };
      });
    };
  };
}
