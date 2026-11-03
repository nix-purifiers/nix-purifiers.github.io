{ lib, model }:
let
  force = value: (builtins.tryEval (builtins.deepSeq value true)).success;
  sample = ../docs-site/projects/ant-purifier.nix;
  withOverride = module: model.evaluateDocumentation [ sample module ];
  checks = {
    realProjectsEvaluate = force model.catalog;
    missingFactFails = !force (model.evaluate [ {
      repository = "example/missing";
    } ]);
    wrongTypeFails = !force (withOverride ({ lib, ... }: {
      facts.lockfiles.value = lib.mkForce true;
    }));
    editorCapabilityRequiresBoolean = !force (withOverride ({ lib, ... }: {
      facts.editor_diagnostics.value = lib.mkForce "jdtls";
    }));
    unknownBlockFails = !force (withOverride {
      sections.editor.blocks.typo.extra-explanation = "Unrecognized block.";
    });
    inactiveBlockProseFails = !force (withOverride ({ lib, ... }: {
      facts.editor_metadata_format.value = lib.mkForce "none";
    }));
    unsupportedEnumFails = !force (withOverride ({ lib, ... }: {
      facts.relock.value = lib.mkForce "sometimes";
    }));
    unknownOptionFails = !force (withOverride { facts.relcok = {}; });
    knownWithoutEvidenceWorks = force (withOverride ({ lib, ... }: {
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
        blocks = lib.mkForce {};
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
    behaviorNeedsNoDocumentation = force (model.evaluate [ ./projects/ant-purifier.nix ]);
    behaviorHasNoPresentationFields = !(model.catalog.ant-purifier ? sections)
      && !(model.catalog.ant-purifier ? summary);
    operationRequiresCapability = !force (withOverride ({ lib, ... }: {
      operations.lock.capability = lib.mkForce null;
    }));
    operationWithoutEvidenceWorks = force (withOverride ({ lib, ... }: {
      operations.lock.sources = lib.mkForce [];
    }));
    duplicateSplicesFail = !force (withOverride ({ lib, ... }: {
      operations.lock.arguments = lib.mkForce [ { splice = "arguments"; } { splice = "arguments"; } ];
    }));
    unknownExpressionFails = !force (withOverride ({ lib, ... }: {
      operations.lock.arguments = lib.mkForce [ { shell = "arbitrary code"; } ];
    }));
    unsupportedOperationCannotHaveRecipe = !force (withOverride {
      operations.lock.state = "unsupported";
      operations.lock.reason = "Unavailable.";
    });
  };
in if builtins.all (x: x) (builtins.attrValues checks) then checks
else throw "Failed model tests: ${lib.concatStringsSep ", " (builtins.attrNames (lib.filterAttrs (_: v: !v) checks))}"
