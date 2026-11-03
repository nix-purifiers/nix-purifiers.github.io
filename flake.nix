{
  description = "Typed purifier behavior catalog and documentation contract";
  inputs.nixpkgs-lib.url = "github:nix-community/nixpkgs.lib";
  outputs = { self, nixpkgs-lib }:
    let
      lib = nixpkgs-lib.lib;
      model = import ./model { inherit lib; };
    in {
      lib = { inherit (model) evaluate; };
      catalog = model.catalog;
      contract = model.contract;
      documentation = { inherit (model) catalog contract; };
      tests = import ./model/tests.nix { inherit lib model; };
    };
}
