# SPDX-License-Identifier: MIT
# Explicit integration check: needs a live Linux Docker daemon. The native
# client and purifier execute on the Nix host, including Darwin. This is an
# external-service host integration derivation, not the pure networkless VM builder.
{
  source,
  dockerHost,
  expectedSystem,
  expectedEngine ? "",
  runtimeId,
}:
let
  self = builtins.getFlake source;
  pkgs =
    import
      (
        if expectedSystem == "x86_64-darwin" then self.inputs.nixpkgs-intel-darwin else self.inputs.nixpkgs
      )
      {
        system = expectedSystem;
      };
  cli = self.packages.${expectedSystem}.default;
  provenance = builtins.fromJSON (builtins.readFile ./fixtures/hello-world/source.json);
  architecture = if pkgs.stdenv.hostPlatform.isx86_64 then "amd64" else "arm64v8";
  upstream =
    name:
    pkgs.fetchurl {
      url = "https://raw.githubusercontent.com/docker-library/hello-world/${provenance.revision}/${architecture}/${name}";
      sha256 = provenance.sha256."${architecture}/${name}";
    };
  sample = pkgs.runCommand "docker-independent-source" { } ''
    mkdir -p "$out"
    cp ${upstream "Dockerfile"} "$out/Dockerfile"
    cp ${upstream "hello"} "$out/hello"
    chmod +x "$out/hello"
  '';
in
pkgs.runCommand "docker-host-runtime-${runtimeId}"
  (
    {
      __noChroot = true;
      preferLocalBuild = true;
      allowSubstitutes = false;
      nativeBuildInputs = [
        pkgs.python3
        pkgs.openssl
        pkgs.nix
        pkgs.git
      ];
      DOCKER_HOST = dockerHost;
      DOCKER_PURIFIER_TEST_RUNTIME_ID = runtimeId;
      EXPECTED_NIX_SYSTEM = expectedSystem;
      EXPECTED_ENGINE_VERSION = expectedEngine;
      DOCKER_PURIFIER_TEST_CLI = cli;
      DOCKER_PURIFIER_TEST_DOCKER = cli.nativeDocker;
      DOCKER_PURIFIER_TEST_SKOPEO = cli.nativeSkopeo;
      DOCKER_PURIFIER_TEST_SOURCE = self.outPath;
      DOCKER_PURIFIER_TEST_SAMPLE = sample;
      DOCKER_PURIFIER_TEST_REVISION = self.rev or self.dirtyRev or "uncommitted";
      SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
      NIX_SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
      NIX_CONFIG = "experimental-features = nix-command flakes\nsandbox = true";
    }
    // pkgs.lib.optionalAttrs pkgs.stdenv.hostPlatform.isDarwin {
      # Darwin always applies a minimal seatbelt profile, even without full
      # sandboxing. Nested local builds cannot initialize another profile.
      # The existing daemon launches their builders outside the parent's profile.
      NIX_REMOTE = "daemon";
    }
  )
  ''
    export HOME="$TMPDIR/check-home"
    mkdir -p "$HOME" "$out"
    python ${./tier2-runtime.py} "$out"
  ''
