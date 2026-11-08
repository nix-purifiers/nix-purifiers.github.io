{ lib, model }:
let
  force = value: (builtins.tryEval (builtins.deepSeq value true)).success;
  sample = ../docs-site/projects/ant-purifier.nix;
  qualityPolicy = import ./quality-policy.nix { inherit lib; };
  humanProof = import ./human-use-review.nix { inherit lib; };
  humanFixture = builtins.fromJSON (builtins.readFile ../docs-site/fixtures/human-use/sbt-firsthand.json);
  technicalMet = lib.genAttrs qualityPolicy.technicalCriteria (_: { state = "met"; });
  humanMissing = { firsthandUse.state = "not-met"; ongoingUse.state = "not-met"; };
  withOverride = module: model.evaluateDocumentation [ sample module ];
  compatibilityPoint = {
    id = "node12";
    components = [ { role = "project-runtime"; name = "Node.js"; version = "12.22.12"; } ];
    system = "x86_64-linux";
    operations = [ "pure-build" ];
    sourceRevision = "1111111111111111111111111111111111111111";
    evidence = [ "https://example.test/test-fixture" ];
    notes = [];
  };
  packagedDefault = {
    role = "native-tool"; name = "Tool"; version = "1.2.3";
    selection = "default"; systems = [ "x86_64-linux" ];
    sourceRevision = compatibilityPoint.sourceRevision;
    evidence = compatibilityPoint.evidence;
  };
  checks = {
    humanContributorSampleReportWorks = force (humanProof.validate "nix-purifiers/sbt-purifier" humanFixture);
    tierThreeRequiresFirsthandHuman = qualityPolicy.bestTier 3 (technicalMet // humanMissing) true == 4;
    firsthandDoesNotProveOngoing = qualityPolicy.bestTier 3
      (technicalMet // humanMissing // { firsthandUse.state = "met"; }) true == 2;
    ongoingUseGatesTierOne = qualityPolicy.bestTier 3
      (technicalMet // { firsthandUse.state = "met"; ongoingUse.state = "met"; }) true == 1;
    botReportCannotProveHumanUse = !force (humanProof.validate "nix-purifiers/sbt-purifier"
      (humanFixture // { reports = humanFixture.reports // {
        sbt-pr-13 = humanFixture.reports.sbt-pr-13 // {
          reporter = humanFixture.reports.sbt-pr-13.reporter // { kind = "bot"; };
        };
      }; }));
    privateOriginalExcludedFromPublicReport =
      let report = humanProof.publicReport { public = humanFixture.reports.sbt-pr-13; private = { statement = "PRIVATE_ORIGINAL"; }; };
      in !(report ? private) && report == humanFixture.reports.sbt-pr-13;
    antCompatibilityDefaultsToCanonicalRegistry =
      (withOverride {}).compatibility.testedPoints ==
        (builtins.fromJSON (builtins.readFile ./compatibility-tests.json)).projects.ant-purifier.testedPoints;
    antCompatibilityAllowsExplicitOverride =
      (withOverride { compatibility.testedPoints = [ compatibilityPoint ]; }).compatibility.testedPoints == [ compatibilityPoint ];
    nixScopeVersionSelectionRoundTrips =
      let
        selection = {
          role = "native-tool-runtime"; name = "JDK"; kind = "nix-scope";
          inputs = [ "nativeProfile" "legacyJvmAdapter" "ant" "apacheIvy" ];
          description = "Explicit live Nix scope configuration.";
          sourceRevision = compatibilityPoint.sourceRevision;
          evidence = compatibilityPoint.evidence;
        };
      in (withOverride { compatibility.projectSelections = [ selection ]; }).compatibility.projectSelections == [ selection ];
    existingVersionSelectionKindsWork = lib.all (kind: force (withOverride {
      compatibility.projectSelections = [ {
        role = "native-tool"; name = "Tool"; inherit kind;
        inputs = [ "selection" ]; description = "An existing selection mechanism.";
        sourceRevision = compatibilityPoint.sourceRevision; evidence = compatibilityPoint.evidence;
      } ];
    })) [ "project-file" "environment" "lockfile" "command-option" ];
    nixScopeVersionSelectionNeedsInputs = !force (withOverride {
      compatibility.projectSelections = [ {
        role = "native-tool-runtime"; name = "JDK"; kind = "nix-scope";
        inputs = []; description = "Missing the actual Nix attributes.";
        sourceRevision = compatibilityPoint.sourceRevision; evidence = compatibilityPoint.evidence;
      } ];
    });
    foreignRepositoryDoesNotInheritTier = (model.evaluateDocumentation [ sample {
      repository = lib.mkForce "other-owner/ant-purifier";
    } ]).quality == null;
    allTierAssessmentsEvaluate = force model.qualityTiers;
    tierPromotionRequiresDarwinAndVersionEvidence = !force (withOverride ({ lib, ... }: {
      quality.tier = lib.mkForce 2;
    }));
    tierThreeRequiresSampleBuild = !force (withOverride ({ lib, ... }: {
      quality.sampleBuilds = lib.mkForce [];
    }));
    tierCriteriaRequireEvidence = !force (withOverride ({ lib, ... }: {
      quality.derivationReview.criteria.linux.derivations = lib.mkForce [];
    }));
    tierFourRequiresEvaluation = !force (withOverride ({ lib, ... }: {
      quality.tier = lib.mkForce 4;
      quality.criteria.evaluation.state = lib.mkForce "not-met";
    }));
    packagedVersionNeedsPlatformScope = !force (withOverride {
      compatibility.defaults = [ (packagedDefault // { systems = []; }) ];
    });
    ambiguousPackagedVersionsFail = !force (withOverride {
      compatibility.defaults = [ packagedDefault (packagedDefault // { version = "2.0.0"; }) ];
    });
    unknownProjectVersionSelectionFails = !force (withOverride {
      compatibility.projectSelections = [ {
        role = "native-tool"; name = "Tool"; kind = "guess";
        inputs = [ "project.conf" ]; description = "Not a known version-selection mechanism.";
        sourceRevision = compatibilityPoint.sourceRevision; evidence = compatibilityPoint.evidence;
      } ];
    });
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
    nativeAndResourceProjectionFormatsWork = force (withOverride ({ lib, ... }: {
      facts.projection_incoming_formats.value = lib.mkForce [ "resources" ];
      facts.projection_outgoing_formats.value = lib.mkForce [ "native" "resources" ];
    }));
    consumerViewIsNotAProjectionFormat = !force (withOverride ({ lib, ... }: {
      facts.projection_outgoing_formats.value = lib.mkForce [ "python-ffi" ];
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
