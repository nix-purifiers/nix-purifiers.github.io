{
  description = "Typed purifier behavior model and its consumers";
  inputs.nixpkgs-lib.url = "github:nix-community/nixpkgs.lib";
  outputs = { self, nixpkgs-lib }:
    let
      lib = nixpkgs-lib.lib;
      model = import ./model { inherit lib; };
      testPlan = import ./model/test-plan.nix { inherit lib; };
      coveragePlan = import ./model/coverage-plan.nix { inherit lib; };
    in {
      lib = { inherit (model) evaluate evaluateDocumentation; inherit testPlan coveragePlan; };
      catalog = model.catalog;
      qualityTiers = model.qualityTiers;
      contract = model.contract;
      documentation = { catalog = model.documentationCatalog; inherit (model) contract; };
      behaviorContract = model.behaviorContract;
      library = builtins.fromJSON (builtins.readFile ./model/library.json);
      testPlans = lib.mapAttrs (_: testPlan) model.catalog;
      coveragePlan = coveragePlan model.catalog;
      tests = import ./model/tests.nix { inherit lib model; };
    };
}
