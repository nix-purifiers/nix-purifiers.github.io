{ lib, ... }:
let
  known = value: { state = "known"; inherit value; };
  definitions = (builtins.fromJSON (builtins.readFile ../contract.json)).facts;
in {
  imports = [ ../operations/sbt.nix ];
  repository = "nix-purifiers/sbt-purifier";
  # Invocation is modeled now; remaining behavioral claims are deliberately
  # unresolved rather than inherited from another JVM tool.
  facts = (lib.genAttrs (builtins.attrNames definitions) (_: {
    state = "unknown";
    reason = "Not yet reviewed for the sbt behavior catalog.";
  })) // {
    tool = known "sbt";
    lockfiles = known [ "sbt-purifier.lock.json" ];
    integration = known "wrapper-and-plugin";
    stale_lock = {
      state = "unknown";
      reason = "A changed definition allows interactive plugin resolution, while prefetch and Nix evaluation stop; a single stale-lock value would conflate those execution modes.";
    };
    relock = {
      state = "unknown";
      reason = "nixLock preserves an unchanged lock but relocks a changed definition; the current two-value vocabulary cannot express this distinction accurately.";
    };
  };
}
