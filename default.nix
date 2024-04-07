{ pkgs
, buildPythonPackage

, libqalculate

, ...
}:

pkgs.stdenv.mkDerivation {
  pname = "qalculate";
  version = "0.0.1";

  src = ./.;

  nativeBuildInputs = with pkgs; [
    pkg-config
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
  ];

  PYQALCULATE_LIBQALCULATE_SOURCE_PATH = "${pkgs.libqalculate.src}";

  buildInputs = [
    libqalculate

    (pkgs.python3Packages.pybind11.overrideAttrs (old: {
      src = builtins.fetchTree {
        type = "github";
        owner = "pybind";
        repo = "pybind11";
        rev = "3e9dfa2866941655c56877882565e7577de6fc7b";
      };
    }))
  ];
}
