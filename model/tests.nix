{ lib, model }:
let
  force = value: (builtins.tryEval (builtins.deepSeq value true)).success;
  sample = ../docs-site/projects/ant-purifier.nix;
  withOverride = module: model.evaluateDocumentation [ sample module ];
  compatibilityPoint = {
    id = "node12";
    components = [ { role = "project-runtime"; name = "Node.js"; version = "12.22.12"; } ];
    system = "x86_64-linux";
    operations = [ "pure-build" ];
    sourceRevision = "1111111111111111111111111111111111111111";
    evidence = [ "https://example.test/test-fixture" ];
  };
  checks = {
    exactCompatibilityPointWorks = force (withOverride {
      compatibility.testedPoints = [ compatibilityPoint ];
    });
    versionRangeCannotBeATestedPoint = !force (withOverride {
      compatibility.testedPoints = [ (compatibilityPoint // {
        components = [ { role = "project-runtime"; name = "Node.js"; version = ">=12"; } ];
      }) ];
    });
    compatibilityRequiresEvidence = !force (withOverride {
      compatibility.testedPoints = [ (compatibilityPoint // { evidence = []; }) ];
    });
    duplicateCompatibilityPointFails = !force (withOverride {
      compatibility.testedPoints = [ compatibilityPoint compatibilityPoint ];
    });
    duplicateCompatibilityComponentFails = !force (withOverride {
      compatibility.testedPoints = [ (compatibilityPoint // {
        components = compatibilityPoint.components ++ compatibilityPoint.components;
      }) ];
    });
    compatibilityRangeNeedsExistingTests = !force (withOverride {
      compatibility.supportedRanges = [ {
        role = "project-runtime"; name = "Node.js"; range = "12.x";
        systems = [ "x86_64-linux" ]; operations = [ "pure-build" ];
        sourceRevision = compatibilityPoint.sourceRevision;
        evidence = compatibilityPoint.evidence;
        basis = "Explicit version compatibility review.";
        supportingTests = [ "absent" ];
      } ];
    });

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
    unsupportedProjectionCannotAdvertiseFormats = !force (withOverride ({ lib, ... }: {
      facts.projection_incoming.value = lib.mkForce "unsupported";
    }));
    supportedProjectionRequiresFormatsAndInterface = !force (withOverride ({ lib, ... }: {
      facts.projection_incoming_formats = lib.mkForce { state = "not-applicable"; reason = "No formats declared."; };
    }));
    cargoAndComposerProjectionFormatsWork = force (withOverride ({ lib, ... }: {
      facts.projection_incoming_formats.value = lib.mkForce [ "cargo" "composer" ];
      facts.projection_outgoing_formats.value = lib.mkForce [ "cargo" "composer" ];
    }));
    unknownProjectionFormatFails = !force (withOverride ({ lib, ... }: {
      facts.projection_incoming_formats.value = lib.mkForce [ "unreviewed-format" ];
    }));
    inactiveBlockProseFails = !force (withOverride ({ lib, ... }: {
      facts.editor_metadata_format.value = lib.mkForce "none";
    }));
    unsupportedEnumFails = !force (withOverride ({ lib, ... }: {
      facts.relock.value = lib.mkForce "sometimes";
    }));
    sectionTitleOverrideFails = !force (withOverride { sections.editor.title = "Editor"; });
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
