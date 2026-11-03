{ lib, ... }: import ../from-record.nix { inherit lib; record = builtins.fromJSON (builtins.readFile ../records/idris2-purifier.json); }
