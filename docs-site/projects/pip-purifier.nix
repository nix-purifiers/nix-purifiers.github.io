{ lib, ... }:
let record = builtins.fromJSON (builtins.readFile ../records/pip-purifier.json);
in {
  imports = [ ../../model/projects/pip-purifier.nix ../profiles/native.nix ];
  inherit (record) summary values;
  sections = lib.mapAttrs (_: section: section // lib.optionalAttrs ((section.mode or "shared") == "omit") { template = lib.mkForce null; }) record.sections;
}
