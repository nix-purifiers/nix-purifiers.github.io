{ lib }:
let
  policy = builtins.fromJSON (builtins.readFile ./tier-policy.json);
  required = tier:
    let rule = policy.tiers.${tier};
    in (if rule ? base then required rule.base else []) ++ rule.requires;
  sample = tier:
    let rule = policy.tiers.${tier};
    in (rule.sampleBuild or false) || (rule ? base && sample rule.base);
in {
  inherit (policy) technicalCriteria humanCriteria labels ongoingUse;
  requireCurrentRegistry = version: if builtins.isInt version && version == 3 then true else throw "Production quality requires registry version 3";
  criterionKeys = version:
    if !(builtins.isInt version) then throw "Unsupported quality registry version"
    else if version == 2 then policy.technicalCriteria
    else if version == 3 then policy.technicalCriteria ++ policy.humanCriteria
    else throw "Unsupported quality registry version";
  bestTier = version: criteria: hasSample:
    if !(builtins.isInt version && builtins.elem version [ 2 3 ]) then throw "Unsupported quality registry version" else
    lib.findFirst (tier:
      (!sample (toString tier) || hasSample)
      && lib.all (key: builtins.hasAttr key criteria && criteria.${key}.state == "met")
        (builtins.filter (key: version == 3 || !(builtins.elem key policy.humanCriteria)) (required (toString tier)))
    ) null [ 1 2 3 4 ];
}
