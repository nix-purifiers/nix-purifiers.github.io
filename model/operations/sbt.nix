{ ... }:
let
  source = "https://github.com/nix-purifiers/sbt-purifier/blob/0e3ae4937ff11f9bd4f268fac2c81e346385ed52/pkgs/sbt-purifier/default.nix";
  task = arguments: {
    capability = "sbt";
    inherit arguments;
    environment.SBT_PURIFIER_LOCKFILE.binding = "lockfile";
    sources = [ source ];
  };
in {
  # `sbt` is a capability supplied by the bespoke integration, with its plugin
  # already installed. These are invocation recipes, not generated glue.
  operations = {
    lock = task [ "-batch" { splice = "arguments"; } "nixLock" ];
    update = task [ "-batch" "nixLockUpdate" ];
    named-update = {
      state = "unsupported";
      reason = "sbt resolves the whole build; nixLockUpdate takes no package names.";
    };
    build = (task [ "-batch" { splice = "arguments"; } "compile" ]) // {
      sources = [ "https://github.com/nix-purifiers/sbt-purifier/blob/0e3ae4937ff11f9bd4f268fac2c81e346385ed52/README.md#quickstart" ];
    };
    test = task [ "-batch" { splice = "arguments"; } "test" ];
    publish = task [ "-batch" { splice = "arguments"; } "nixPublish" ];
    prefetch = {
      capability = "sbt-purifier";
      arguments = [ "prefetch" ];
      environment.SBT_PURIFIER_LOCKFILE.binding = "lockfile";
      sources = [ source ];
    };
  };
}
