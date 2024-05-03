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
              rev = "6473679b7b419740f72d396a305734382de6e821";
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
