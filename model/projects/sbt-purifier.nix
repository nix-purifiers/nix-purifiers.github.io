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
    projection_incoming = known "conditional";
    projection_incoming_formats = known [ "Maven" ];
    projection_incoming_interfaces = known [ "projectDependencies" "nixFlakeRepositories" ];
    projection_incoming_limits = known [ "The typed projectDependencies path requires a Maven projection and inferred module catalog; an Ivy view may accompany it" "Legacy sbtRepositories outputs and raw repository overrides use separate compatibility paths" ];
    projection_outgoing = known "conditional";
    projection_outgoing_formats = known [ "Maven" "Ivy" ];
    projection_outgoing_interfaces = known [ "packages.<id>.projections.maven" "packages.<id>.projections.ivy" "projections.maven" ];
    projection_outgoing_limits = known [ "Package-level Ivy projections are available only when all variants use Ivy publications (no POM artifacts)" "The aggregate projections output exports Maven only" ];
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
