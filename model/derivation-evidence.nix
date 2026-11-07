# Typed local-realization receipts; completed-review semantics are enforced separately.
{ lib }:
let
  inherit (lib) mkOption types;
  text = types.addCheck types.str (s: builtins.match ".*[^ \n\t].*" s != null);
  sha = types.strMatching "[0-9a-f]{40}";
  digest = types.strMatching "sha256-[A-Za-z0-9+/]{43}=";
  system = types.enum [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
  store = types.strMatching "/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+";
  outputs = types.attrsOf store;
  hashes = types.attrsOf digest;
  sdks = types.attrsOf text;
  option = type: mkOption { inherit type; };
  sampleSources = types.listOf (types.submodule { options = {
    repository = option (types.strMatching ''https://[^[:space:]<>"|]+'');
    revision = option sha;
    sourceNarHash = option digest;
  }; });
  check = types.submodule { options = {
    kind = option (types.enum [ "flake-attribute" "expression" ]);
    value = option text;
    replay = option (types.nullOr (types.submodule { options = {
      artifactUrl = option (types.strMatching ''https://[^[:space:]<>"|]+'');
      artifactSha256 = option (types.strMatching "[0-9a-f]{64}");
      expressionSha256 = option (types.strMatching "[0-9a-f]{64}");
      arguments = option sdks;
    }; }));
  }; };
in {
  # Cross-field integrity and judgment rules live in validate_review, not this type.
  derivation = types.submodule {
    options = {
      repository = option (types.strMatching "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+");
      revision = option sha;
      system = option system;
      check = option check;
      drvPath = option (types.strMatching "/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+\\.drv");
      outputs = option outputs;
      outputNarHashes = option hashes;
      sourceNarHash = option digest;
      sdkVersions = option sdks;
      sampleSources = option sampleSources;
      evaluation = option (types.nullOr (types.submodule { options = {
        sourceRevision = option sha;
        sourceNarHash = option digest;
        check = option check;
        drvPath = option store;
        receipt = option (types.strMatching ''https://[^[:space:]<>"|]+'');
        artifactSha256 = option (types.strMatching "[0-9a-f]{64}");
      }; }));
      build = option (types.nullOr (types.submodule { options = {
        status = option (types.enum [ "success" "failed" "blocked" ]);
        executedSystem = option system;
        sourceRevision = option sha;
        sourceNarHash = option digest;
        drvPath = option store;
        outputs = option outputs;
        outputNarHashes = option hashes;
        sdkVersions = option sdks;
        sampleSources = option sampleSources;
        receipt = option (types.strMatching ''https://[^[:space:]<>"|]+'');
        artifactSha256 = option (types.strMatching "[0-9a-f]{64}");
      }; }));
    };
  };
  criterion = types.submodule { options = {
    state = option (types.enum [ "met" "not-met" ]);
    summary = option text;
    derivations = option (types.listOf text);
    sources = option (types.listOf (types.strMatching ''https://[^[:space:]<>"|]+''));
    gap = option (types.nullOr text);
  }; };
}
