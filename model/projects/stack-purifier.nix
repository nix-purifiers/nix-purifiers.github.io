{ lib, ... }: import ../from-record.nix { inherit lib; record = builtins.fromJSON (builtins.readFile ../records/stack-purifier.json); }
