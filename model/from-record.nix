{ lib, record }:
let definitions = (builtins.fromJSON (builtins.readFile ./contract.json)).facts;
in {
  inherit (record) repository reviewedRevision operations;
  compatibility = record.compatibility or {};
  facts = lib.genAttrs (builtins.attrNames definitions) (_: {
    state = "unknown";
    reason = "This capability is not established by the reviewed integration record.";
  }) // record.facts;
}
