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
            version = "unstable-2023-05-02";
            src = "" + builtins.fetchTree {
              type = "github";
              owner = "Qalculate";
              repo = "libqalculate";
              rev = "87d7a3d37223021e60ea4436b4f4a3ace0224a1e";
            };
          });
        };
        # For testing USE_SYSTEM_QALCULATE=OFF
        devShells.default = self.packages."${system}".default.overrideAttrs (old: {
          nativeBuildInputs = old.nativeBuildInputs ++ self.packages."${system}".libqalculate.nativeBuildInputs;
          buildInputs = old.buildInputs ++ self.packages."${system}".libqalculate.buildInputs;
        });
      });
}
