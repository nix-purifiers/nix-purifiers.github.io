# Unintegrated native CI variant. Retained captures are checked locally, not fetched.
{ lib }:
let
  inherit (lib) mkOption types;
  text = types.addCheck types.str (s: builtins.match ".*[^ \n\t].*" s != null);
  opt = type: mkOption { inherit type; };
  store = types.strMatching "/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+";
  url = types.strMatching ''https://[^[:space:]<>"|]+'';
  ref = types.submodule { options = {
    receipt = opt url;
    format = mkOption { type = types.enum [ "command-json" "job-json" "jobs-json" "json" "text" ]; default = "command-json"; };
    artifactSha256 = opt (types.strMatching "[0-9a-f]{64}");
  }; };
  runners = {
    ubuntu-24_04-arm = "aarch64-linux";
    ubuntu-24_04 = "x86_64-linux";
    ubuntu-22_04 = "x86_64-linux";
    macos-14-arm64 = "aarch64-darwin";
    macos-15-arm64 = "aarch64-darwin";
    macos-14 = "x86_64-darwin";
    macos-15 = "x86_64-darwin";
    macos-26-arm64 = "aarch64-darwin";
  };
  runnerSystem = image: runners.${lib.replaceStrings [ "." ] [ "_" ] image} or null;
  scriptShape = types.submodule { options = {
    kind = opt (types.enum [ "script-generated-derivation" ]);
    scriptPath = opt (types.strMatching "[A-Za-z0-9_./-]+\\.(py|sh)");
    sourceUrl = opt url;
    scriptArtifact = opt ref;
    lockArtifact = opt ref;
    invoker = opt text;
    arguments = opt types.str;
    inputSourceHashes = opt (types.attrsOf (types.strMatching "[0-9a-f]{64}"));
    replayNotes = opt text;
    assertionSnippet = opt text;
    executionArtifact = mkOption { type = types.nullOr ref; default = null; };
    reportArtifact = mkOption { type = types.nullOr ref; default = null; };
    artifactMetadata = mkOption { type = types.nullOr ref; default = null; };
    buildArgv = mkOption { type = types.nullOr (types.listOf text); default = null; };
    transcriptLayout = mkOption { type = types.nullOr (types.enum [ "argv-stdout-stderr" ]); default = null; };
    artifactName = mkOption { type = types.nullOr text; default = null; };
  }; };
  shape = types.submodule { options = {
    kind = opt (types.enum [ "native-ci-execution" ]);
    repository = opt (types.strMatching "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+");
    revision = opt (types.strMatching "[0-9a-f]{40}");
    system = opt (types.enum [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ]);
    check = opt (types.either (types.strMatching "checks\\.[a-z0-9_-]+\\.[a-zA-Z0-9_.-]+") scriptShape);
    drvPath = opt (types.strMatching "/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+\\.drv");
    sourceNarHash = mkOption { type = types.nullOr (types.strMatching "sha256-[A-Za-z0-9+/]{43}="); default = null; };
    stepName = mkOption { type = types.nullOr text; default = null; };
    logJobName = mkOption { type = types.nullOr text; default = null; };
    sdkVersions = mkOption { type = types.attrsOf text; default = {}; };
    sampleSources = mkOption { default = []; type = types.listOf (types.submodule { options = {
      repository = opt url;
      revision = opt (types.strMatching "[0-9a-f]{40}");
      sourceNarHash = opt (types.strMatching "sha256-[A-Za-z0-9+/]{43}=");
    }; }); };
    predictedOutputs = opt (types.attrsOf store);
    observedOutputs = opt (types.attrsOf store);
    outputNarHashes = opt (types.nullOr (types.attrsOf text));
    jobUrl = opt url;
    jobArtifact = opt ref;
    logArtifact = opt ref;
    stepNumber = opt types.int;
    command = opt text;
    jobConclusion = mkOption { type = types.nullOr (types.enum [ "success" "failure" ]); default = null; };
    runtimeAssertions = mkOption { type = types.listOf text; default = []; };
    runnerImage = opt text;
  }; };
  esc = builtins.fromJSON ''"\u001b"'';
  clean = value: lib.concatStrings (builtins.filter builtins.isString (builtins.split "(${esc}|\\^\\[)\\[[0-9;]*m" value));
in {
  inherit shape;
  validate = directory: publicBase: record:
    let
      e = (lib.evalModules { modules = [{ options.value = opt shape; } { value = record; }]; }).config.value;
      capture = reference:
        let suffix = if reference.format == "text" then ".log" else ".json";
            path = directory + "/${reference.artifactSha256}${suffix}";
            raw = builtins.readFile path;
        in if reference.receipt == lib.removeSuffix "/" publicBase + "/${reference.artifactSha256}${suffix}"
          && builtins.hashFile "sha256" path == reference.artifactSha256
        then (if reference.format == "text" then raw else builtins.fromJSON raw)
        else throw "Native CI retained artifact mismatch";
      jc = capture e.jobArtifact;
      lc = capture e.logArtifact;
      jobMatches = if e.jobArtifact.format == "jobs-json" then builtins.filter (j: j.html_url == e.jobUrl) jc.jobs else [];
      job = if e.jobArtifact.format == "command-json" then builtins.fromJSON jc.stdout
        else if e.jobArtifact.format == "jobs-json" then builtins.head jobMatches else jc;
      api = "repos/${e.repository}/actions/jobs/${toString job.id}";
      matches = builtins.filter (s: s.number == e.stepNumber) job.steps;
      step = builtins.head matches;
      rawLog = if e.logArtifact.format == "text" then lc else lc.stdout;
      selected = if e.logJobName == null then rawLog else
        lib.concatStringsSep "\n" (map (line: lib.concatStringsSep "\t" (lib.drop 2 (lib.splitString "\t" line)))
          (builtins.filter (line: lib.hasPrefix "${e.logJobName}\t" line && builtins.length (lib.splitString "\t" line) >= 3) (lib.splitString "\n" rawLog))) + "\n";
      log = clean selected;
      lines = map (line:
        let parts = lib.splitString " " line; in {
          time = builtins.substring 0 19 (builtins.head parts);
          payload = lib.concatStringsSep " " (builtins.tail parts);
        }) (lib.splitString "\n" log);
      laterSteps = builtins.filter (s: s.number > e.stepNumber && (s.started_at or null) != null) job.steps;
      bounded = map (line: line.payload) (builtins.filter (line:
        line.time >= builtins.substring 0 19 step.started_at && line.time <= builtins.substring 0 19 step.completed_at
        && lib.all (s: line.time < builtins.substring 0 19 s.started_at) laterSteps
      ) lines);
      scripted = builtins.isAttrs e.check;
      pair = if scripted then null else "checking derivation ${e.check}...";
      pairing = lib.foldl' (state: line:
        if lib.hasPrefix "checking derivation " line then state // { pending = line; }
        else if lib.hasPrefix "derivation evaluated to " line then {
          pending = null;
          matched = state.matched || (state.pending == pair && line == "derivation evaluated to ${e.drvPath}");
        } else state
      ) { pending = null; matched = false; } bounded;
      logical = lib.foldl' (state: line:
        let part = lib.strings.trim line; in
        if lib.hasSuffix "\\" part then state // { pending = state.pending + lib.strings.trim (lib.removeSuffix "\\" part) + " "; }
        else { pending = ""; completed = state.completed ++ [ (state.pending + part) ]; }
      ) { pending = ""; completed = []; } bounded;
      archived = scripted && e.check.executionArtifact != null;
      transcript = if archived then capture e.check.executionArtifact else null;
      report = if archived then capture e.check.reportArtifact else null;
      artifactMatches = if archived then builtins.filter (a: a.name == e.check.artifactName) (capture e.check.artifactMetadata).artifacts else [];
      archive = builtins.head artifactMatches;
      proofLines = if archived then lib.splitString "\n" (clean transcript) else bounded;
      archiveValid = !archived || (e.check.reportArtifact != null && e.check.artifactMetadata != null && e.check.artifactName != null
        && builtins.isString transcript && builtins.isAttrs report && (report.selectedCasesPassed or false) == true
        && builtins.length artifactMatches == 1 && archive.workflow_run.id == job.run_id && archive.workflow_run.head_sha == e.revision
        && lib.hasInfix archive.name log && builtins.substring 0 19 archive.created_at >= builtins.substring 0 19 step.completed_at);
      indexed = lib.imap0 (index: line: { inherit index line; }) proofLines;
      builtMarkers = builtins.filter (x: x.line == "building '${e.drvPath}'...") indexed;
      structured = scripted && e.check.transcriptLayout == "argv-stdout-stderr";
      parsedArgv = line:
        let parsed = if lib.hasPrefix "[" line then builtins.tryEval (builtins.fromJSON line) else { success = false; value = null; };
        in if parsed.success && builtins.isList parsed.value && parsed.value != [] && lib.all builtins.isString parsed.value
          then parsed.value else null;
      blockState = lib.foldl' (state: line:
        let argv = parsedArgv line; in
        if argv != null then {
          blocks = state.blocks ++ lib.optional (state.current != null) state.current;
          current = { inherit argv; lines = []; };
        } else state // { current = if state.current == null then null else state.current // { lines = state.current.lines ++ [ line ]; }; }
      ) { blocks = []; current = null; } proofLines;
      commandBlocks = blockState.blocks ++ lib.optional (blockState.current != null) blockState.current;
      validObservedBinding = if structured then lib.any (block:
        block.argv == e.check.buildArgv && builtins.elem "building '${e.drvPath}'..." block.lines
        && lib.all (path: builtins.elem path block.lines) (builtins.attrValues e.observedOutputs)
      ) commandBlocks else builtMarkers != [] && lib.all (path:
        lib.any (x: x.index > (builtins.head builtMarkers).index && x.line == path) indexed
      ) (builtins.attrValues e.observedOutputs);
      validScript =
        let c = e.check;
            generator = capture c.scriptArtifact;
            lock = capture c.lockArtifact;
            expectedCommand = "${c.invoker} ${c.scriptPath}" + lib.optionalString (c.arguments != "") " ${c.arguments}";
        in c.sourceUrl == "https://github.com/${e.repository}/blob/${e.revision}/${c.scriptPath}"
        && !(builtins.elem ".." (lib.splitString "/" c.scriptPath))
        && e.sourceNarHash != null && e.sdkVersions != {}
        && builtins.match "(nix shell [^;&|]+ -c )?(python3( -B)?|bash|sh)" c.invoker != null
        && e.command == expectedCommand && lib.all (token: !lib.hasInfix token expectedCommand) [ ";" "&&" "||" "\n" ]
        && (c.inputSourceHashes.${c.scriptPath} or null) == c.scriptArtifact.artifactSha256
        && (c.inputSourceHashes."flake.lock" or null) == c.lockArtifact.artifactSha256
        && builtins.isString generator && generator != "" && builtins.isAttrs lock && (lock.version or null) == 7 && builtins.isAttrs (lock.nodes or null)
        && lib.hasInfix c.assertionSnippet generator
        && ((c.buildArgv == null && c.transcriptLayout == null) || (structured && archived && c.buildArgv != null
          && lib.take 2 c.buildArgv == [ "nix" "build" ] && lib.hasInfix "result.stdout + result.stderr" generator))
        && validObservedBinding
        && builtMarkers != [] && lib.all (assertion: lib.any (x: x.index > (builtins.head builtMarkers).index && x.line == assertion) indexed) e.runtimeAssertions;
      valid = archiveValid && lib.all (name: builtins.match ".*[^ \n\t].*" name != null) (builtins.attrNames e.sdkVersions)
        && e.outputNarHashes == null && (e.observedOutputs == {} || archived)
        && lib.all (name: builtins.match ".*[^ \n\t].*" name != null) (builtins.attrNames e.observedOutputs)
        && lib.all (path: !lib.hasSuffix ".drv" path) (builtins.attrValues e.observedOutputs)
        && lib.all (name: builtins.match ".*[^ \n\t].*" name != null) (builtins.attrNames e.predictedOutputs)
        && lib.all (p: !lib.hasSuffix ".drv" p) (builtins.attrValues e.predictedOutputs)
        && (if scripted then validScript else lib.hasPrefix "checks.${e.system}." e.check && builtins.elem e.command [ "nix flake check -L" "nix flake check --print-build-logs" "nix flake check" ]) && runnerSystem e.runnerImage == e.system
        && builtins.elem e.jobArtifact.format [ "command-json" "job-json" "jobs-json" ] && builtins.elem e.logArtifact.format [ "text" "command-json" ]
        && (if e.jobArtifact.format == "command-json" then jc.exitCode == 0 && jc.command == [ "gh" "api" api ]
          else (e.jobArtifact.format != "jobs-json" || builtins.length jobMatches == 1) && job.url == "https://api.github.com/${api}")
        && (e.logArtifact.format == "text" || (lc.exitCode == 0 && builtins.elem lc.command [ [ "gh" "api" "${api}/logs" ] [ "gh" "api" "${api}/logs" "--allow-escape-sequences" ] ]))
        && (e.logJobName == null || e.logJobName == job.name)
        && job.head_sha == e.revision && job.html_url == e.jobUrl
        && lib.hasPrefix "https://github.com/${e.repository}/actions/runs/" e.jobUrl
        && job.status == "completed" && builtins.elem job.conclusion [ "success" "failure" ]
        && (job.conclusion != "failure" || e.jobConclusion == "failure")
        && (e.jobConclusion == null || e.jobConclusion == job.conclusion)
        && builtins.length matches == 1 && step.status == "completed" && step.conclusion == "success"
        && step.name == (if e.stepName == null then "Run ${e.command}" else e.stepName) && builtins.elem e.command logical.completed
        && lib.hasInfix e.revision log
        && (lib.hasInfix "repository: ${e.repository}" log || lib.hasInfix "Syncing repository: ${e.repository}" log)
        && lib.hasInfix "Image: ${e.runnerImage}\n" log && (scripted || pairing.matched);
    in builtins.deepSeq e (if valid then e else throw "Native CI execution binding mismatch");
}
