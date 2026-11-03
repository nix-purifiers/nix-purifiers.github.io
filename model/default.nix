{ lib }:
let
  behaviorContract = builtins.fromJSON (builtins.readFile ./contract.json);
  contract = (builtins.fromJSON (builtins.readFile ../docs-site/contract.json)) // {
    inherit (behaviorContract) facts;
  };
  exportFacts = cfg: lib.mapAttrs (_: f:
    if f.state == "known" then { inherit (f) state value sources; }
    else { inherit (f) state reason; }
  ) cfg.facts;
  validateProjections = cfg:
    if lib.all (direction:
      let
        support = cfg.facts.${"projection_${direction}"};
        formats = cfg.facts.${"projection_${direction}_formats"};
        interfaces = cfg.facts.${"projection_${direction}_interfaces"};
      in support.state != "known" || (
        if support.value == "unsupported" then
          formats.state == "not-applicable" && interfaces.state == "not-applicable"
        else formats.state == "known" && interfaces.state == "known"
      )
    ) [ "incoming" "outgoing" ] then cfg
    else throw "Projection support must agree with declared formats and interfaces";
  evaluate = modules:
    let cfg = validateProjections (lib.evalModules { modules = [ ./schema.nix ] ++ modules; }).config;
    in { version = 1; inherit (cfg) repository operations; facts = exportFacts cfg; };
  evaluateDocumentation = modules:
    let
      cfg = validateProjections (lib.evalModules { modules = [ ./schema.nix ./documentation.nix ] ++ modules; }).config;
      specifications = lib.listToAttrs (map (s: lib.nameValuePair s.id s) contract.sections);
      expectedSections = builtins.attrNames specifications;
      sections = lib.mapAttrs (key: section:
        let
          template = specifications.${key}.shared.${section.template};
          blocks = if builtins.isString template then [ { id = "main"; } ] else template;
          blockNames = map (b: b.id) blocks;
          active = block:
            lib.all (k: facts.${k}.state == "known") (block.whenKnown or [])
            && lib.all (k:
              let required = block.when.${k};
              in facts.${k}.state == "known" && builtins.elem facts.${k}.value
                (if builtins.isList required then required else [ required ])
            ) (builtins.attrNames (block.when or {}));
          extraBlocks = builtins.attrNames section.blocks;
        in
        if section.mode == "shared" then
          if section.template == null || section.reason != null then
            throw "Shared sections require a template and cannot have a replacement reason"
          else if !(builtins.hasAttr section.template specifications.${key}.shared) then
            throw "${key}: unknown shared template ${section.template}"
          else if !(lib.all (name: builtins.elem name blockNames) extraBlocks) then
            throw "${key}: prose targets an unknown block"
          else if !(lib.all (block: !(builtins.elem block.id extraBlocks) || active block) blocks) then
            throw "${key}: prose targets an inactive conditional block"
          else if !(lib.all (factKey:
            let
              required = specifications.${key}.requires.${section.template}.${factKey};
              choices = if builtins.isList required then required else [ required ];
              fact = facts.${factKey};
            in fact.state == "known" && builtins.elem fact.value choices
          ) (builtins.attrNames (specifications.${key}.requires.${section.template} or {}))) then
            throw "${key}: shared template contradicts declared facts"
          else { use = section.template; }
            // lib.optionalAttrs (section.details != null) { inherit (section) details; }
            // lib.optionalAttrs (section.blocks != {}) {
              blocks = lib.mapAttrs (_: prose: lib.filterAttrs (_: v: v != null) prose) section.blocks;
            }
        else if section.mode == "replace" then
          if section.reason == null || section.details == null || section.template != null || section.blocks != {} then
            throw "Replacements require details and reason, without a template"
          else { replace = section.details; inherit (section) reason; }
        else if section.reason == null || section.details != null || section.template != null || section.blocks != {} then
          throw "Omissions require a reason and cannot contain copy"
        else { omit = section.reason; }
      ) cfg.sections;
      facts = exportFacts cfg;
    in if builtins.attrNames cfg.sections != expectedSections then
      throw "Every project must explicitly cover the contract sections: ${lib.concatStringsSep ", " expectedSections}"
    else { version = 1; inherit (cfg) repository summary operations; inherit facts sections; };
  catalog = lib.genAttrs [ "ant-purifier" "docker-purifier" "sbt-purifier" ] (name:
    evaluate [ (./projects + "/${name}.nix") ]);
  documentationCatalog = lib.mapAttrs (name: _: evaluateDocumentation [
    (../docs-site/projects + "/${name}.nix")
  ]) (lib.filterAttrs (name: _: builtins.pathExists (../docs-site/projects + "/${name}.nix")) catalog);
in { inherit evaluate evaluateDocumentation catalog documentationCatalog contract behaviorContract; }
