{ lib, ... }:
let record = builtins.fromJSON (builtins.readFile ../records/package-el-purifier.json);
in {
  imports = [ ../../model/projects/package-el-purifier.nix ../profiles/native.nix ];
  inherit (record) summary values;
  sections = lib.mapAttrs (_: section: section // lib.optionalAttrs ((section.mode or "shared") == "omit") { template = lib.mkForce null; }) record.sections;
}
