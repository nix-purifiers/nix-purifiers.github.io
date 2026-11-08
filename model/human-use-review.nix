# Structural review integrity; original human statements are reviewed separately.
{ lib }:
let
  inherit (lib) mkOption types;
  policy = import ./quality-policy.nix { inherit lib; };
  opt = type: mkOption { inherit type; };
  whitespace = (builtins.fromJSON (builtins.readFile ./tier-policy.json)).humanWhitespace;
  withoutWhitespace = s: builtins.replaceStrings whitespace (map (_: "") whitespace) s;
  nonblank = s: builtins.stringLength (withoutWhitespace s) > 0;
  text = types.addCheck types.str nonblank;
  primaryUrl = types.addCheck types.str (u:
    builtins.match ''https://[^<>"|]+'' u != null && withoutWhitespace u == u);
  date = types.strMatching "[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])";
  nullable = type: types.nullOr type;
  report = types.submodule { options = {
    repository = opt (types.strMatching "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+");
    reportedAt = opt date;
    reviewedAt = opt date;
    reporter = opt (types.submodule { options = {
      kind = opt (types.enum [ "human" "bot" "unknown" ]);
      relationship = opt (types.enum [ "maintainer" "contributor" "independent-user" "other-user" "unknown" ]);
      publicLabel = opt (nullable text);
    }; });
    basis = opt (types.enum [ "firsthand" "hearsay" "authorship-only" "automation" ]);
    scope = opt text;
    summary = opt text;
    claims = opt (types.listOf (types.enum [ "firsthand-use" "ongoing-use" ]));
    source = opt (types.submodule { options = {
      kind = opt (types.enum [ "public-primary-url" "direct-attestation" ]);
      url = opt (nullable (primaryUrl));
      reference = opt (nullable (types.strMatching "[A-Za-z0-9][A-Za-z0-9_.:-]*"));
    }; });
  }; };
  usageContext = types.submodule { options = {
    repository = opt (types.strMatching "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+");
    kind = opt (types.enum [ "maintained-consumer-history" "supplied-usage-context" ]);
    scope = opt text;
    attribution = opt text;
    reviewedAt = opt date;
    source = opt (types.submodule { options = {
      kind = opt (types.enum [ "public-primary-url" "private-context" ]);
      url = opt (nullable (primaryUrl));
      reference = opt (nullable (types.strMatching "[A-Za-z0-9][A-Za-z0-9_.:-]*"));
    }; });
  }; };
  validContext = repository: c: c.repository == repository
    && (if c.source.kind == "public-primary-url" then c.source.url != null && c.source.reference == null
        else c.source.url == null && c.source.reference != null);
  criterion = types.submodule { options = {
    state = opt (types.enum [ "met" "not-met" ]);
    summary = opt text;
    reports = opt (types.listOf text);
    gap = opt (nullable text);
    confidenceReason = opt (nullable text);
    usageContexts = opt (types.listOf usageContext);
  }; };
  unique = xs: builtins.length xs == builtins.length (lib.unique xs);
  validReport = repository: r:
    r.repository == repository && r.claims != [] && unique r.claims
    && (!(builtins.elem "ongoing-use" r.claims) || builtins.elem "firsthand-use" r.claims)
    && (if r.source.kind == "public-primary-url" then r.source.url != null && r.source.reference == null
        else r.source.url == null && r.source.reference != null);
  checkedReport = repository: value:
    let r = (lib.evalModules { modules = [{ options.r = opt report; config.r = value; }]; }).config.r;
    in builtins.deepSeq r (if validReport repository r then r else throw "Invalid reviewed human report");
in {
  validateReport = checkedReport;
  publicReport = envelope:
    if !(envelope ? public) || !lib.all (key: builtins.elem key [ "public" "private" ]) (builtins.attrNames envelope)
    then throw "Attestation envelope needs an explicit public projection"
    else checkedReport envelope.public.repository envelope.public;
  validate = repository: value:
    let
      q = (lib.evalModules { modules = [{ options.q = opt (types.submodule { options = {
        reviewedAt = opt date;
        reports = opt (types.attrsOf report);
        criteria = lib.genAttrs policy.humanCriteria (_: opt criterion);
      }; }); config.q = value; }]; }).config.q;
      validCriterion = key:
        let c = q.criteria.${key}; refs = c.reports;
            contexts = c.usageContexts;
        in unique refs && lib.all (ref: builtins.hasAttr ref q.reports) refs
          && lib.all (validContext repository) contexts && (key == "ongoingUse" || contexts == [])
          && (if c.state == "not-met" then c.gap != null && c.confidenceReason == null else
            c.gap == null && (key != "firsthandUse" || refs != [])
            && lib.all (ref: let r = q.reports.${ref}; in
              r.reporter.kind == "human" && r.basis == "firsthand" && builtins.elem "firsthand-use" r.claims) refs
            && (if key == "ongoingUse" then c.confidenceReason != null && q.criteria.firsthandUse.state == "met"
              && (contexts != [] || (refs != [] && lib.all (ref: builtins.elem "ongoing-use" q.reports.${ref}.claims) refs))
                else c.confidenceReason == null));
      valid = lib.all nonblank (builtins.attrNames q.reports) && lib.all (r: validReport repository r) (builtins.attrValues q.reports)
        && lib.all validCriterion policy.humanCriteria;
    in builtins.deepSeq q (if valid then q else throw "Invalid reviewed human usage evidence");
}
