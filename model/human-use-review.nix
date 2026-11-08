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
  roleBasis = types.submodule { options = {
    summary = opt text;
    source = opt (types.submodule { options = {
      kind = opt (types.enum [ "public-primary-url" "direct-attestation" "private-context" ]);
      url = opt (nullable primaryUrl);
      reference = opt (nullable (types.strMatching "[A-Za-z0-9][A-Za-z0-9_.:-]*"));
    }; });
  }; };
  ongoingUser = types.submodule { options = {
    publicLabel = opt (nullable text);
    maintainerStatus = opt (types.enum [ "maintainer" "non-maintainer" "unknown" ]);
    statusBasis = opt (nullable roleBasis);
    useScope = opt text;
  }; };
  validRoleBasis = b: if b.source.kind == "public-primary-url" then b.source.url != null && b.source.reference == null
    else b.source.url == null && b.source.reference != null;
  validUser = u: (u.statusBasis == null || validRoleBasis u.statusBasis)
    && (u.maintainerStatus == "unknown" || u.statusBasis != null);
  maintainerOngoing = users: lib.any (u: u.maintainerStatus == policy.ongoingUse.requiredMaintainerStatus) users;
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
    ongoingUsers = opt (types.listOf ongoingUser);
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
    ongoingUsers = opt (types.listOf ongoingUser);
    reviewedAt = opt date;
    source = opt (types.submodule { options = {
      kind = opt (types.enum [ "public-primary-url" "private-context" ]);
      url = opt (nullable (primaryUrl));
      reference = opt (nullable (types.strMatching "[A-Za-z0-9][A-Za-z0-9_.:-]*"));
    }; });
  }; };
  validContext = repository: c: c.repository == repository && lib.all validUser c.ongoingUsers
    && (if c.source.kind == "public-primary-url" then c.source.url != null && c.source.reference == null
        else c.source.url == null && c.source.reference != null);
  canonicalRepository = repositoryRoot: value:
    let
      clean = builtins.head (lib.splitString "?" (builtins.head (lib.splitString "#" value)));
      matched = builtins.match "https://([A-Za-z0-9.-]+)/([A-Za-z0-9._~/-]+)" clean;
    in if matched == null then null else let
      originalHost = lib.toLower (builtins.elemAt matched 0);
      originalPath = lib.toLower (builtins.elemAt matched 1);
      api = originalHost == "api.github.com" && lib.hasPrefix "repos/" originalPath;
      host = if originalHost == "www.github.com" || api then "github.com" else originalHost;
      path = lib.removeSuffix ".git" (lib.removeSuffix "/" (if api then lib.removePrefix "repos/" originalPath else originalPath));
      segments = lib.splitString "/" path;
    in if lib.any (part: builtins.elem part [ "" "." ".." ]) segments
      || (repositoryRoot && host == "github.com" && builtins.length segments != 2)
      then null else "https://${host}/${path}";
  projectIdentity = p:
    let base = canonicalRepository true p.publicRepository; path = p.projectPath;
    in if base == null then null else if path == null then base else
      if builtins.match "[A-Za-z0-9._~/-]+" path == null || lib.any (part: builtins.elem part [ "" "." ".." ]) (lib.splitString "/" path)
      then null else base + "#" + lib.toLower path;
  belongs = url: project:
    let value = canonicalRepository false url; base = canonicalRepository true project.publicRepository;
    in value != null && base != null && (value == base || lib.hasPrefix (base + "/") value);
  publicProof = extra: types.submodule { options = {
    projectIdentity = opt text;
    sourceUrl = opt primaryUrl;
    summary = opt text;
  } // extra; };
  consumerProject = types.submodule { options = {
    repository = opt (types.strMatching "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+");
    canonicalIdentity = opt text;
    publicRepository = opt primaryUrl;
    projectPath = opt (nullable text);
    identityBasis = opt text;
    kind = opt (types.enum [ "external-open-source-consumer" ]);
    reviewedAt = opt date;
    vitalityConfidence = opt text;
    externalAdoption = opt (types.submodule { options = {
      projectIdentity = opt text;
      status = opt (types.enum [ "reviewed-beyond-maintainer" ]);
      summary = opt text;
      source = opt (types.submodule { options = {
        kind = opt (types.enum [ "public-primary-url" "direct-attestation" "private-context" ]);
        url = opt (nullable primaryUrl);
        reference = opt (nullable (types.strMatching "[A-Za-z0-9][A-Za-z0-9_.:-]*"));
      }; });
    }; });
    openSourceBasis = opt (publicProof {});
    integration = opt (publicProof { kind = opt (types.enum [ "actual-purifier-integration" ]); });
    activityMonitoring = opt (types.listOf (publicProof { kind = opt (types.enum
      (policy.ongoingUse.substantiveActivityKinds ++ policy.ongoingUse.supplementalActivityKinds)); }));
  }; };
  validConsumer = repository: p:
    let identity = projectIdentity p;
        proofBelongs = proof: proof.projectIdentity == identity && belongs proof.sourceUrl p;
        adoption = p.externalAdoption;
    in p.repository == repository && identity != null && p.canonicalIdentity == identity
      && canonicalRepository true p.publicRepository != "https://github.com/${lib.toLower repository}"
      && adoption.projectIdentity == identity && validRoleBasis adoption
      && (adoption.source.kind != "public-primary-url" || belongs adoption.source.url p)
      && proofBelongs p.openSourceBasis && proofBelongs p.integration
      && p.activityMonitoring != [] && lib.all proofBelongs p.activityMonitoring
      && lib.any (a: builtins.elem a.kind policy.ongoingUse.substantiveActivityKinds) p.activityMonitoring;
  criterion = types.submodule { options = {
    state = opt (types.enum [ "met" "not-met" ]);
    summary = opt text;
    reports = opt (types.listOf text);
    gap = opt (nullable text);
    confidenceReason = opt (nullable text);
    usageContexts = opt (types.listOf usageContext);
    consumerProjects = opt (types.listOf consumerProject);
  }; };
  unique = xs: builtins.length xs == builtins.length (lib.unique xs);
  validReport = repository: r:
    r.repository == repository && r.claims != [] && unique r.claims
    && lib.all validUser r.ongoingUsers
    && (r.ongoingUsers == [] || builtins.elem "ongoing-use" r.claims)
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
            contexts = c.usageContexts; projects = c.consumerProjects;
        in unique refs && lib.all (ref: builtins.hasAttr ref q.reports) refs
          && lib.all (validContext repository) contexts && lib.all (validConsumer repository) projects
          && unique (map (p: p.canonicalIdentity) projects)
          && (key == "ongoingUse" || (contexts == [] && projects == []))
          && (if c.state == "not-met" then c.gap != null && c.confidenceReason == null else
            c.gap == null && (key != "firsthandUse" || refs != [])
            && lib.all (ref: let r = q.reports.${ref}; in
              r.reporter.kind == "human" && r.basis == "firsthand" && builtins.elem "firsthand-use" r.claims) refs
            && (if key == "ongoingUse" then c.confidenceReason != null && q.criteria.firsthandUse.state == "met"
              && builtins.length projects >= policy.ongoingUse.minimumConsumerProjects
              && (lib.any (c: maintainerOngoing c.ongoingUsers) contexts
                || lib.any (ref: let r = q.reports.${ref}; in builtins.elem "ongoing-use" r.claims && maintainerOngoing r.ongoingUsers) refs)
                else c.confidenceReason == null));
      valid = lib.all nonblank (builtins.attrNames q.reports) && lib.all (r: validReport repository r) (builtins.attrValues q.reports)
        && lib.all validCriterion policy.humanCriteria;
    in builtins.deepSeq q (if valid then q else throw "Invalid reviewed human usage evidence");
}
