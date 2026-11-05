{ lib, record }:
let
  definitions = (builtins.fromJSON (builtins.readFile ./contract.json)).facts;
  evidence = builtins.fromJSON (builtins.readFile ./compatibility-tests.json);
  name = builtins.baseNameOf record.repository;
  points = (evidence.projects.${name} or { testedPoints = []; }).testedPoints;
in {
  inherit (record) repository reviewedRevision operations;
  compatibility = (record.compatibility or {}) // { testedPoints = points; };
  facts = lib.genAttrs (builtins.attrNames definitions) (_: {
    state = "unknown";
    reason = "This capability is not established by the reviewed integration record.";
  }) // record.facts;
}
