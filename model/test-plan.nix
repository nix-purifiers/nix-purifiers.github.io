{ lib }:
model:
let
  relock = model.facts.relock;
  lockAvailable = (model.operations.lock.state or "unknown") == "available";
  nativeTestsAvailable = (model.operations.test.state or "unknown") == "available";
  cases = lib.optionalAttrs (relock.state == "known" && lockAvailable) {
    relock = {
      kind = "relock";
      fact = "relock";
      expectUnchanged = relock.value == "preserves-pins";
      capabilities = [ model.operations.lock.capability ];
      fixtures = [ "locked-selections" "advance-upstream" ];
    };
  } // lib.optionalAttrs nativeTestsAvailable {
    native-tests = {
      kind = "operation";
      operation = "test";
      capabilities = [ model.operations.test.capability ];
      fixtures = [];
    };
  };
in {
  inherit (model) repository;
  inherit cases;
  # A declared fact is not a passed test. Publish gaps alongside the plan.
  uncoveredFacts = builtins.filter (name:
    !(name == "relock" && cases ? relock)
  ) (builtins.attrNames model.facts);
}
