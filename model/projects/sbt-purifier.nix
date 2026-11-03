{ lib, ... }:
let
  source = "https://github.com/nix-purifiers/sbt-purifier/blob/0e3ae4937ff11f9bd4f268fac2c81e346385ed52/README.md";
  known = anchor: value: { state = "known"; inherit value; sources = [ "${source}#${anchor}" ]; };
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
    tool = known "quickstart" "sbt";
    lockfiles = known "quickstart" [ "sbt-purifier.lock.json" ];
    integration = known "without-the-wrapper" "wrapper-and-plugin";
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
