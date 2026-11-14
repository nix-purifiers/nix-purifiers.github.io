{ lib }:
catalog:
let
  # Bind the generated obligations to behavior, not presentation or test results.
  catalogInputs = lib.mapAttrs (_: model: {
    inherit (model) repository facts operations;
    reviewedRevision = model.reviewedRevision or null;
  }) catalog;
  known = model: name: (model.facts.${name}.state or "unknown") == "known";
  value = model: name: fallback: if known model name then model.facts.${name}.value else fallback;
  projection = model: direction:
    let name = "projection_${direction}";
    in if !(known model name) then "needs-review"
    else if model.facts.${name}.value == "unsupported" then "not-applicable" else "required";
  both = model:
    let states = map (projection model) [ "incoming" "outgoing" ];
    in if builtins.elem "not-applicable" states then "not-applicable"
    else if builtins.elem "needs-review" states then "needs-review" else "required";
  obligation = id: applicability: facts: observations: {
    inherit id applicability facts observations;
    # Obligations describe required coverage; they never attest execution.
    execution = "not-run";
  };
  lifecycle = model:
    let applicable = if (model.operations.lock.state or "unknown") == "available" then "required" else "needs-review";
    in map (transition: obligation "lifecycle.${transition}" applicable [ "lockfiles" ] [
      "native-selection" "native-execution" "pure-build" "publication-membership" "stale-entry-removal"
    ]) [ "initial" "dependency-bump" "dependency-add" "dependency-drop" ]
    ++ map (transition: obligation "lifecycle.${transition}" (projection model "incoming")
      [ "projection_incoming" "projection_incoming_formats" "projection_incoming_interfaces" ]
      [ "native-selection" "artifact-origin" "pure-build" "outgoing-consumer" "stale-entry-removal" ]
    ) [ "native-to-nix" "nix-to-native" ]
    ++ map (transition: obligation "lifecycle.${transition}" "needs-review" [ "build_outputs" ]
      [ "buildable-membership" "pure-build" "publication-membership" "stale-entry-removal" ]
    ) [ "buildable-add" "buildable-drop" ];
  perProject = model: {
    inherit (model) repository;
    reviewedRevision = model.reviewedRevision or null;
    systems = value model "platforms" [];
    # Native SDK support is not currently structured in the behavior model.
    # Keep this gap explicit rather than treating host execution as all SDKs.
    sdkMatrix = { state = "needs-review"; reason = "Native SDK versions and resolver backends require reviewed metadata."; };
    cacheProfiles = [ "cold" "warm" "explicit-update" ];
    obligations = lifecycle model ++ [
      (obligation "projection.incoming" (projection model "incoming")
        [ "projection_incoming" "projection_incoming_formats" "projection_incoming_interfaces" ]
        [ "native-selection" "artifact-origin" "pure-build" ])
      (obligation "projection.outgoing-ordinary" (projection model "outgoing")
        [ "projection_outgoing" "projection_outgoing_formats" "projection_outgoing_interfaces" ]
        [ "ordinary-resolution" "ordinary-execution" "no-purifier-integration" ])
      (obligation "sandwich.purifier-ordinary-purifier" (both model)
        [ "projection_incoming" "projection_outgoing" ]
        [ "ordinary-publication" "downstream-eviction" "return-native-selection" "return-pure-build" ])
      (obligation "sandwich.ordinary-purifier-ordinary" (projection model "outgoing")
        [ "projection_outgoing" ]
        [ "ordinary-input" "pure-build" "outgoing-publication" "ordinary-resolution" "ordinary-execution" ])
      (obligation "graph.transitive-evictions" "required" [ "lockfiles" ]
        [ "complete-selected-graph" "diamond" "evicted-node-dependencies" "native-execution" ])
      (obligation "graph.multiple-nix-references" (projection model "incoming")
        [ "projection_incoming" ]
        [ "shared-transitive" "reversed-input-order" "conflicting-providers" "lock-preserved-on-failure" ])
      (obligation "graph.republication-evictions" (projection model "outgoing")
        [ "projection_outgoing" ]
        [ "ordinary-publication" "downstream-own-eviction" "transitive-origin" "ordinary-execution" ])
      ((obligation "resolver.maven-managed-override"
        (if !(known model "projection_outgoing_formats") then projection model "outgoing"
         else if builtins.elem "maven" (value model "projection_outgoing_formats" []) then "required" else "not-applicable")
        [ "projection_outgoing" "projection_outgoing_formats" ]
        [ "soft-request-preserves-nix" "incompatible-hard-request-rejected" "explicit-exclusion-origin-loss-detected" "same-bytes-native-coordinate" ]) // {
          expectedOutcome = "hard-constraints-survive-unless-explicitly-excluded";
          reason = "Soft native requests must respect exact hard ranges in projected POMs; incompatible hard ranges must fail. Explicit exclusion removes the transitive constraint and requires an origin-loss observation.";
        })
    ];
  };
  # Matching format names generate candidates, never a compatibility claim.
  edges = lib.concatMap (producer: lib.concatMap (consumer:
    let p = catalog.${producer}; c = catalog.${consumer};
        formats = lib.intersectLists (value p "projection_outgoing_formats" [])
          (value c "projection_incoming_formats" []);
    in lib.concatMap (format: lib.concatMap (outgoingInterface:
      map (incomingInterface: {
        inherit producer consumer format outgoingInterface incomingInterface;
        status = "candidate";
        systems = lib.intersectLists (value p "platforms" []) (value c "platforms" []);
        producerLimits = value p "projection_outgoing_limits" [];
        consumerLimits = value c "projection_incoming_limits" [];
        adopterSequences = [ [ "purifier" "purifier" "ordinary" ]
          [ "purifier" "ordinary" "purifier" "ordinary" ] ];
        execution = "not-run";
      }) (value c "projection_incoming_interfaces" [])
    ) (value p "projection_outgoing_interfaces" [])) formats
  ) (builtins.attrNames catalog)) (builtins.attrNames catalog);
in {
  version = 1;
  scope = "coverage-obligations";
  catalogDigest = builtins.hashString "sha256" (builtins.toJSON catalogInputs);
  projects = lib.mapAttrs (_: perProject) catalog;
  projectionCandidates = edges;
  formatPolicies.maven = {
    nativeConflictPolicy = "hard-version-requirements-then-nearest-soft-selection";
    supportsExactHardVersionRanges = true;
    sources = [ "https://maven.apache.org/pom.html"
      "https://maven.apache.org/guides/introduction/introduction-to-dependency-mechanism.html" ];
  };
}
