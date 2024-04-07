{ pkgs
, buildPythonPackage

, libqalculate

, ...
}:

# FIXME: AFAIK this is still not really a viable python package
#        I think this has to be built for specific python versions instead?
pkgs.stdenv.mkDerivation (self: {
  pname = "qalculate";
  version = "0.0.1";

  src = ./.;

  nativeBuildInputs = with pkgs; [
    pkg-config
    cmake
    python3

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
    zip
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

  cmakeFlags = [
    "-DLIBQALCULATE_SOURCE_PATH=${libqalculate.src}"
  ];

  installPhase = ''
    mkdir -p "$out/lib/python3.11"
    cp -Lr qalculate-${self.version}-cp311-cp311-linux_x86_64 "$out/lib/python3.11/site-packages"
  '';
})
