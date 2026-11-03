{ lib, ... }:
let record = builtins.fromJSON (builtins.readFile ../records/spago-purifier.json);
in {
  imports = [ ../../model/projects/spago-purifier.nix ../profiles/native.nix ];
  inherit (record) summary values;
  sections = lib.mapAttrs (_: section: section // lib.optionalAttrs ((section.mode or "shared") == "omit") { template = lib.mkForce null; }) record.sections;
}
