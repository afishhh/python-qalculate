{
  description = "A basic flake";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    with flake-utils.lib;
    eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      with pkgs.lib; {
        packages.libqalculate =pkgs.libqalculate.overrideAttrs (old: {
          version = "unstable-2023-04-06";
          src = "" + (builtins.fetchTree {
            type = "github";
            owner = "Qalculate";
            repo = "libqalculate";
            rev = "f87048ddad81135049517b64d9f145ec83d08859";
          });
        });

        devShell = pkgs.mkShell {
          nativeBuildInputs = with pkgs; [
            bashInteractive
            mypy
          ];

          buildInputs = with pkgs; [
            (pkgs.python3Packages.buildPythonApplication {
              pname = "pybind11-stubgen";
              version = "2.5.1";
              src = builtins.fetchTree {

                type = "github";
                owner = "sizmailov";
                repo = "pybind11-stubgen";
                rev = "cf58aa6c7f0655c2f830b6964aa48baff868b891";

              };
              dontWrapPythonPrograms = true;
            })
            self.packages.${pkgs.system}.libqalculate
            (python3Packages.pybind11.overrideAttrs (old: {
              src = builtins.fetchTree {
                type = "github";
                owner = "pybind";
                repo = "pybind11";
                rev = "3e9dfa2866941655c56877882565e7577de6fc7b";
              };
            }))
            python3
            # (pkgs.callPackage ./qalculate-static.nix {})
          ];

          shellHook = ''
            export NIX_CFLAGS_COMPILE="$NIX_CFLAGS_COMPILE -I${pkgs.python3}/include/python3.11"
          '';
        };
      });
}
