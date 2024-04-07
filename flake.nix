{
  description = "Python bindings for libqalculate";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    with flake-utils.lib;
    eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        packages = {
          default = pkgs.python3Packages.callPackage ./default.nix {
            inherit (self.packages.${system}) libqalculate;
          };
          libqalculate = pkgs.libqalculate.overrideAttrs (old: {
            version = "unstable-2023-04-07";
            src = "" + builtins.fetchTree {
              type = "github";
              owner = "Qalculate";
              repo = "libqalculate";
              rev = "3d2b5dc3b3dce43e0e7b8e222c738bead571ad67";
            };
          });
        };
      });
}
