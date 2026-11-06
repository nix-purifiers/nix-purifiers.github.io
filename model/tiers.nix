{ config, lib, ... }:
let
  inherit (lib) mkOption types;
  registry = builtins.fromJSON (builtins.readFile ./tiers.json);
  name = builtins.baseNameOf config.repository;
  text = types.addCheck types.str (s: builtins.match ".*[^ \n\t].*" s != null);
  sources = types.listOf (types.strMatching "https://[^ ]+");
  criterion = types.submodule {
    options = {
      state = mkOption { type = types.enum [ "met" "not-met" "unreviewed" ]; };
      summary = mkOption { type = text; };
      evidence = mkOption { type = sources; default = []; };
    };
  };
  keys = [ "evaluation" "goodTests" "linux" "darwin" "oneVersion" "nonEolVersions" "manySamples" "longCompatibility" ];
  assessment = types.submodule {
    options = {
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
    in base && q.tier == best && lib.all (key:
      !met key || q.criteria.${key}.evidence != []
    ) keys;
in {
  options.quality = mkOption {
    type = types.nullOr assessment;
    default = if config.repository == "nix-purifiers/${name}"
      then registry.projects.${name} or null else null;
    apply = q: if q == null || valid q then q
      else throw "Purifier tier must match its evidenced criteria; evaluation and met criteria require evidence";
  };
}
