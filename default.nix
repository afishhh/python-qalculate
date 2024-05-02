{ pkgs

, pkg-config
, cmake
, python3
, python3Packages
, libqalculate

, ...
}:

# FIXME: AFAIK this is still not really a viable python package
#        I think this has to be built for specific python versions instead?
pkgs.stdenv.mkDerivation (self: {
  pname = "qalculate";
  version = "0.0.1";

  src = ./.;

  nativeBuildInputs = [
    pkg-config
    cmake
    python3

    (python3Packages.buildPythonApplication {
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

    python3Packages.pytest
  ];

  buildInputs = [
    libqalculate

    (python3Packages.pybind11.overrideAttrs (old: {
      src = builtins.fetchTree {
        type = "github";
        owner = "pybind";
        repo = "pybind11";
        rev = "3e9dfa2866941655c56877882565e7577de6fc7b";
      };
    }))
  ];

  LIBQALCULATE_SOURCE_PATH = "${pkgs.libqalculate.src}";

  installPhase = ''
    mkdir -p "$out/lib/python3.11"
    cp -r qalculate-${self.version}-cp311-cp311-linux_x86_64 "$out/lib/python3.11/site-packages"
  '';
})
