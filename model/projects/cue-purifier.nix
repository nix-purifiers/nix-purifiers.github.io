{ lib, ... }: import ../from-record.nix { inherit lib; record = builtins.fromJSON (builtins.readFile ../records/cue-purifier.json); }
