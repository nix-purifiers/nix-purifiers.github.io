# Structural receipt integrity only. The integrator authenticates actual artifacts.
{ lib, artifactDirectory ? ../docs-site/evidence, publicBase ? "https://nix-purifiers.github.io/evidence/" }:
let
  inherit (lib) mkOption types;
  shape = import ./derivation-evidence.nix { inherit lib; };
  keys = [ "evaluation" "goodTests" "linux" "darwin" "oneVersion" "nonEolVersions" "manySamples" "longCompatibility" ];
  text = types.addCheck types.str (s: builtins.match ".*[^ \n\t].*" s != null);
  url = types.strMatching ''https://[^[:space:]<>"|]+'';
  opt = type: mkOption { inherit type; };
  ci = import ./native-ci-evidence.nix { inherit lib; };
  isCI = e: (e.kind or null) == "native-ci-execution";
  native = e: if isCI e then builtins.deepSeq (ci.validate artifactDirectory publicBase e) true else e.build != null && e.build.status == "success" && e.build.executedSystem == e.system;
  nonblank = s: builtins.match ".*[^ \n\t].*" s != null;
  named = attrs: lib.all nonblank (builtins.attrNames attrs);
  unique = xs: builtins.length xs == builtins.length (lib.unique xs);
  validLocalEvidence = repository: revision: e:
    e.repository == repository && e.revision == revision
    && named e.outputs && named e.sdkVersions
    && lib.all (k: e.outputs ? ${k}) (builtins.attrNames e.outputNarHashes)
    && (if e.check.kind == "expression" then e.check.replay != null
      && named e.check.replay.arguments
      && e.check.replay.expressionSha256 == builtins.hashString "sha256" e.check.value
      else e.check.replay == null)
    && e.outputs != {}
    && lib.all (p: !lib.hasSuffix ".drv" p) (builtins.attrValues e.outputs)
    && (e.evaluation == null || (
      e.evaluation.sourceRevision == e.revision && e.evaluation.sourceNarHash == e.sourceNarHash
      && e.evaluation.check == e.check && e.evaluation.drvPath == e.drvPath))
    && (if e.build == null then e.outputNarHashes == {} else let b = e.build; in
      b.sourceRevision == e.revision && b.sourceNarHash == e.sourceNarHash
      && b.drvPath == e.drvPath && b.sdkVersions == e.sdkVersions && b.sampleSources == e.sampleSources
      && (if b.status == "success" then b.outputs == e.outputs && b.outputNarHashes == e.outputNarHashes
        && builtins.attrNames e.outputNarHashes == builtins.attrNames e.outputs
        else b.outputs == {} && b.outputNarHashes == {} && e.outputNarHashes == {}));
  validEvidence = repository: revision: e:
    if isCI e then builtins.deepSeq (ci.validate artifactDirectory publicBase e)
      (e.repository == repository && e.revision == revision)
    else builtins.deepSeq ((lib.evalModules { modules = [{ options.e = opt shape.derivation; config.e = e; }]; }).config.e)
      (validLocalEvidence repository revision e);
in {
  validate = repository: revision: review:
    let
      q = (lib.evalModules { modules = [{ options = {
        derivations = opt (types.attrsOf types.attrs);
        criteria = lib.genAttrs keys (_: opt shape.criterion);
        sampleBuilds = opt (types.listOf (types.submodule { options = {
          name = opt text;
          upstream = opt (types.submodule { options = {
            repository = opt url;
            revision = opt (types.strMatching "[0-9a-f]{40}");
            sourceNarHash = opt (types.strMatching "sha256-[A-Za-z0-9+/]{43}=");
          }; });
          derivations = opt (types.listOf text);
        }; }));
      }; } review]; }).config;
      validRefs = refs: unique refs && lib.all (ref: builtins.hasAttr ref q.derivations) refs;
      validSample = s: s.derivations != [] && validRefs s.derivations && lib.all (ref: native q.derivations.${ref} && builtins.elem s.upstream (q.derivations.${ref}.sampleSources or [])) s.derivations;
      validCriterion = key:
        let c = q.criteria.${key}; bound = map (ref: q.derivations.${ref}) c.derivations; in
        validRefs c.derivations && (if c.state == "not-met" then c.gap != null && (c.derivations != [] || c.sources != []) else
          c.gap == null && c.derivations != []
          && (if key == "evaluation" then lib.all (e: isCI e || e.evaluation != null || (e.build != null && e.build.status == "success")) bound else lib.all native bound)
          && (!(builtins.elem key [ "linux" "darwin" ]) || lib.all (e: lib.hasSuffix ("-" + key) e.system) bound)
          && (!(builtins.elem key [ "oneVersion" "nonEolVersions" "longCompatibility" ]) || lib.all (e: (e.sdkVersions or {}) != {}) bound)
          && (key != "nonEolVersions" || c.sources != [])
          && (key != "manySamples" || (q.sampleBuilds != [] && lib.all (ref: lib.any (s: builtins.elem ref s.derivations) q.sampleBuilds) c.derivations)));
      valid = named q.derivations && lib.all (validEvidence repository revision) (builtins.attrValues q.derivations)
        && lib.all validSample q.sampleBuilds
        && unique (map (s: s.name) q.sampleBuilds)
        && lib.all validCriterion keys;
    in builtins.deepSeq q (if valid then q else throw "Invalid completed derivation review bindings");
}
