{
  description = "Typed purifier behavior model and its consumers";
  inputs.nixpkgs-lib.url = "github:nix-community/nixpkgs.lib";
  outputs = { self, nixpkgs-lib }:
    let
      lib = nixpkgs-lib.lib;
      model = import ./model { inherit lib; };
      testPlan = import ./model/test-plan.nix { inherit lib; };
    in {
      lib = { inherit (model) evaluate evaluateDocumentation; inherit testPlan; };
      catalog = model.catalog;
      contract = model.contract;
      documentation = { catalog = model.documentationCatalog; inherit (model) contract; };
      behaviorContract = model.behaviorContract;
      testPlans = lib.mapAttrs (_: testPlan) model.catalog;
      tests = import ./model/tests.nix { inherit lib model; };
    };
}
