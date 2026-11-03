{ ... }:
let
  source = "https://github.com/nix-purifiers/docker-purifier/blob/186edeb4dd1bb0c9806485368b64cd5c1433fac3/docker_purifier/cli.py";
  resolve = arguments: {
    capability = "docker-purifier";
    inherit arguments;
    environment.DOCKER_PURIFIER_LOCKFILE.binding = "lockfile";
    sources = [ source ];
  };
in {
  operations = {
    lock = resolve [ "lock" ];
    update = resolve [ "update" ];
    named-update = (resolve [ "update" { splice = "arguments"; } ]) // { minimumArguments = 1; };
    prefetch = resolve [ "prefetch" ];
    build = {
      capability = "docker";
      arguments = [ "build" { splice = "arguments"; } "." ];
      environment.DOCKER_PURIFIER_LOCKFILE.binding = "lockfile";
      sources = [ source ];
    };
    test = { state = "unsupported"; reason = "Docker has no universal test command; image tests must be supplied by the project integration."; };
    publish = resolve [ "publish" { splice = "arguments"; } ];
  };
}
