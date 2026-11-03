{ lib, ... }:
let record = builtins.fromJSON (builtins.readFile ../records/jb-purifier.json);
in {
  imports = [ ../../model/projects/jb-purifier.nix ../profiles/native.nix ];
  inherit (record) summary values;
  sections = lib.mapAttrs (_: section: section // lib.optionalAttrs ((section.mode or "shared") == "omit") { template = lib.mkForce null; }) record.sections;
}
