{ lib, model }:
let
  force = value: (builtins.tryEval (builtins.deepSeq value true)).success;
  sample = ./projects/ant-purifier.nix;
  withOverride = module: model.evaluate [ sample module ];
  checks = {
    realProjectsEvaluate = force model.catalog;
    missingFactFails = !force (model.evaluate [ {
      repository = "example/missing"; summary = "Missing facts."; sections = {};
    } ]);
    wrongTypeFails = !force (withOverride ({ lib, ... }: {
      facts.lockfiles.value = lib.mkForce true;
    }));
    unsupportedEnumFails = !force (withOverride ({ lib, ... }: {
      facts.relock.value = lib.mkForce "sometimes";
    }));
    unknownOptionFails = !force (withOverride { facts.relcok = {}; });
    knownWithoutEvidenceFails = !force (withOverride ({ lib, ... }: {
      facts.relock.sources = lib.mkForce [];
    }));
    unknownWithValueFails = !force (withOverride ({ lib, ... }: {
      facts.relock.state = lib.mkForce "unknown";
      facts.relock.reason = "Needs investigation.";
    }));
    replacementWithoutReasonFails = !force (withOverride ({ lib, ... }: {
      sections.editor.mode = "replace";
      sections.editor.template = lib.mkForce null;
    }));
    explicitOmissionWorks = force (withOverride ({ lib, ... }: {
      sections.editor = {
        mode = "omit"; reason = "No editor integration.";
        template = lib.mkForce null; details = lib.mkForce null;
      };
    }));
    unknownTemplateFails = !force (withOverride {
      sections.workflow.template = "alternative";
    });
    contradictoryTemplateFails = !force (withOverride ({ lib, ... }: {
      facts.relock.value = lib.mkForce "re-resolves";
    }));
    missingSectionFails = !force (withOverride ({ lib, ... }: {
      sections = lib.mkForce {};
    }));
    explicitDifferenceWorks = force (withOverride ({ lib, ... }: {
      facts.relock.value = lib.mkForce "re-resolves";
      sections.workflow = {
        mode = "replace"; template = lib.mkForce null;
        details = lib.mkForce "Relocking resolves dependencies again.";
        reason = "This integration does not preserve pins.";
      };
    }));
    sharedVariantWorks = (withOverride ({ lib, ... }: {
      facts.relock.value = lib.mkForce "re-resolves";
      sections.workflow.template = "fresh";
    })).sections.workflow.use == "fresh";
  };
in if builtins.all (x: x) (builtins.attrValues checks) then checks
else throw "Failed model tests: ${lib.concatStringsSep ", " (builtins.attrNames (lib.filterAttrs (_: v: !v) checks))}"
