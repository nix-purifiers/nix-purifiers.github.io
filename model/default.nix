{ lib }:
let
  contract = builtins.fromJSON (builtins.readFile ../docs-site/contract.json);
  evaluate = modules:
    let
      cfg = (lib.evalModules { modules = [ ./schema.nix ] ++ modules; }).config;
      specifications = lib.listToAttrs (map (s: lib.nameValuePair s.id s) contract.sections);
      expectedSections = builtins.attrNames specifications;
      sections = lib.mapAttrs (key: section:
        if section.mode == "shared" then
          if section.template == null || section.reason != null then
            throw "Shared sections require a template and cannot have a replacement reason"
          else if !(builtins.hasAttr section.template specifications.${key}.shared) then
            throw "${key}: unknown shared template ${section.template}"
          else if !(lib.all (factKey:
            let
              required = specifications.${key}.requires.${section.template}.${factKey};
              choices = if builtins.isList required then required else [ required ];
              fact = facts.${factKey};
            in fact.state == "known" && builtins.elem fact.value choices
          ) (builtins.attrNames (specifications.${key}.requires.${section.template} or {}))) then
            throw "${key}: shared template contradicts declared facts"
          else { use = section.template; } // lib.optionalAttrs (section.details != null) { inherit (section) details; }
        else if section.mode == "replace" then
          if section.reason == null || section.details == null || section.template != null then
            throw "Replacements require details and reason, without a template"
          else { replace = section.details; inherit (section) reason; }
        else if section.reason == null || section.details != null || section.template != null then
          throw "Omissions require a reason and cannot contain copy"
        else { omit = section.reason; }
      ) cfg.sections;
      facts = lib.mapAttrs (_: f:
        if f.state == "known" then { inherit (f) state value sources; }
        else { inherit (f) state reason; }
      ) cfg.facts;
    in if builtins.attrNames cfg.sections != expectedSections then
      throw "Every project must explicitly cover the contract sections: ${lib.concatStringsSep ", " expectedSections}"
    else { version = 1; inherit (cfg) repository summary; inherit facts sections; };
  catalog = lib.genAttrs [ "ant-purifier" "docker-purifier" ] (name:
    evaluate [ (./projects + "/${name}.nix") ]);
in { inherit evaluate catalog contract; }
