{ ... }:
let
  source = "https://github.com/nix-purifiers/docker-purifier/blob/186edeb4dd1bb0c9806485368b64cd5c1433fac3/README.md";
in {
  imports = [ ../../model/projects/docker-purifier.nix ../profiles/locked-wrapper.nix ];
  summary = "Locked, Nix-resolved base images for Docker builds.";
  sections = {
    quickstart.blocks.commands.extra-explanation = ''
      Pass `-t my-app` to the build if you want to run it with `docker run --rm my-app`.
    '';
    offline.blocks.main.extra-explanation = ''
      Host `RUN` commands retain network access. Vendor their inputs or prepare
      package caches before using `docker build --network=none`.
    '';
    nix_builds.blocks.vm.extra-explanation = ''
      Neither host root privileges nor KVM is required. Software emulation adds
      overhead. Use the pinned nixpkgs or a compatible `vmTools` interface.
      See [builder configuration](${source}#optional-nix-build).
    '';
    scope.blocks.unsupported.extra-explanation = ''
      See [troubleshooting and external locks](${source}#troubleshooting).
    '';
  };
}
