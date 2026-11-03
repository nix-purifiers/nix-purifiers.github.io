{ ... }:
let
  source = "https://github.com/nix-purifiers/ant-purifier/blob/793373015c1a35f49877d222939b771b1e52aa9b/ant_purifier/cli.py";
  resolve = arguments: {
    capability = "ant-purifier";
    inherit arguments;
    environment.ANT_PURIFIER_LOCKFILE.binding = "lockfile";
    sources = [ source ];
  };
in {
  operations = {
    editor = {
      capability = "jdtls";
      environment.ANT_PURIFIER_LOCKFILE.binding = "lockfile";
      sources = [ source ];
    };
    lock = resolve [ "lock" ];
    update = resolve [ "update" ];
    named-update = (resolve [ "update" { splice = "arguments"; } ]) // { minimumArguments = 1; };
    prefetch = resolve [ "prefetch" ];
    build = { capability = "ant"; arguments = [ { splice = "arguments"; } "test" ]; environment.ANT_PURIFIER_LOCKFILE.binding = "lockfile"; sources = [ source ]; };
    test = { capability = "ant"; arguments = [ "test" ]; environment.ANT_PURIFIER_LOCKFILE.binding = "lockfile"; sources = [ source ]; };
    publish = {
      state = "unknown";
      reason = "Native publication targets are project-specific; no common invocation is modeled yet.";
    };
  };
}
