{ lib

, pkg-config
, cmake

, buildPythonPackage
, pytest
, pybind11
, libqalculate

, ...
}:

buildPythonPackage rec {
  pname = "qalculate";
  version = "0.0.1";
  format = "other";

  src = builtins.path {
    name = "python-qalculate-src";
    path = ./.;
    filter = path: type:
      let
        relative = lib.removePrefix "${builtins.toString ./.}/" path;
        filtered = [
          "src.*"
          "generate.*"
          "cmake.*"
          "CMakeLists.txt"
        ];
      in
      builtins.any (pattern: builtins.match pattern relative != null) filtered;
  };

  nativeBuildInputs = [
    pkg-config
    cmake
    pytest
  ];

  buildInputs = [
    libqalculate
    pybind11
  ];

  LIBQALCULATE_SOURCE_PATH = "${libqalculate.src}";

  installPhase = ''
    python_version=$(python3 -c "print(__import__('sysconfig').get_python_version())")
    python_version2=$(python3 -c 'print("'"$python_version"'".replace(".", ""))')
    mkdir -p "$out/lib/python$python_version"
    cp -r "qalculate-${version}-cp''${python_version2}-cp''${python_version2}-linux_x86_64" "$out/lib/python$python_version/site-packages"
  '';
}
