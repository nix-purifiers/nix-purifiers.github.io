{ lib, ... }:
let record = builtins.fromJSON (builtins.readFile ../records/carton-purifier.json);
in {
  imports = [ ../../model/projects/carton-purifier.nix ../profiles/native.nix ];
  inherit (record) summary values;
  sections = lib.mapAttrs (_: section: section // lib.optionalAttrs ((section.mode or "shared") == "omit") { template = lib.mkForce null; }) record.sections;
}
