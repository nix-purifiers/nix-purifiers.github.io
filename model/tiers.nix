let
  registry = builtins.fromJSON (builtins.readFile ./tiers.json);
  artifacts = builtins.fromJSON (builtins.readFile ./review-artifacts.json);
  retained = r:
    let hash = r.artifactSha256; suffix = if (r.format or "") == "text" then ".log" else ".json"; path = ../docs-site/evidence + "/${hash}${suffix}";
    in builtins.match "[0-9a-f]{64}" hash != null
      && r.receipt == "https://nix-purifiers.github.io/evidence/${hash}${suffix}"
      && builtins.pathExists path && builtins.hashString "sha256" (builtins.readFile path) == hash;
  originals = builtins.all (group: builtins.all retained (builtins.attrValues group)) (builtins.attrValues artifacts);
in { config, lib, ... }:
let
  inherit (lib) mkOption types;
  name = builtins.baseNameOf config.repository;
  proof = import ./derivation-review.nix { inherit lib; };
  text = types.addCheck types.str (s: builtins.match ".*[^ \n\t].*" s != null);
  sources = types.listOf (types.strMatching "https://[^ ]+");
  criterion = types.submodule {
    options = {
      state = mkOption { type = types.enum [ "met" "not-met" ]; };
      summary = mkOption { type = text; };
      evidence = mkOption { type = sources; default = []; };
    };
  };
  keys = [ "evaluation" "goodTests" "linux" "darwin" "oneVersion" "nonEolVersions" "manySamples" "longCompatibility" ];
  assessment = types.submodule {
    options = {
      derivationReview = mkOption { type = types.attrs; };
      tier = mkOption { type = types.ints.between 1 4; };
      reviewedRevision = mkOption { type = types.strMatching "[0-9a-f]{40}"; };
      reviewedAt = mkOption { type = types.strMatching "[0-9]{4}-[0-9]{2}-[0-9]{2}"; };
      rationale = mkOption { type = text; };
      criteria = lib.genAttrs keys (_: mkOption { type = criterion; });
      sampleBuilds = mkOption {
        default = [];
        type = types.listOf (types.submodule { options = {
          name = mkOption { type = text; };
          evidence = mkOption { type = types.addCheck sources (xs: xs != []); };
        }; });
      };
    };
  };
  valid = q:
    let
      met = key: q.criteria.${key}.state == "met";
      base = met "evaluation";
      third = base && q.sampleBuilds != [] && met "linux" && met "oneVersion";
      second = third && met "goodTests" && met "darwin" && met "nonEolVersions";
      first = third && met "goodTests" && met "darwin" && met "manySamples" && met "longCompatibility";
      best = if first then 1 else if second then 2 else if third then 3 else 4;
      review = proof.validate config.repository q.reviewedRevision q.derivationReview;
      receipts = lib.all (e:
        if (e.kind or null) == "native-ci-execution" then true else
        (e.evaluation == null || retained e.evaluation)
        && (e.build == null || retained e.build)
        && (e.check.replay == null || retained {
          receipt = e.check.replay.artifactUrl;
          artifactSha256 = e.check.replay.artifactSha256;
        })
      ) (builtins.attrValues review.derivations);
      same = lib.all (key: q.criteria.${key}.state == review.criteria.${key}.state
        && q.criteria.${key}.summary == review.criteria.${key}.summary) keys
        && map (s: s.name) q.sampleBuilds == map (s: s.name) review.sampleBuilds;
    in builtins.deepSeq review (registry.version == 2 && originals && receipts && same && base && q.tier == best);
in {
  options.quality = mkOption {
    type = types.nullOr assessment;
    default = if config.repository == "nix-purifiers/${name}"
      then registry.projects.${name} or null else null;
    apply = q: if q == null || valid q then q
      else throw "Purifier tier must match its evidenced criteria; evaluation and met criteria require evidence";
  };
}
