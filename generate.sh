#!/usr/bin/env bash

set -euo pipefail

nix build .#libqalculate.src --out-link libqalculate-source
python3 generate.py libqalculate-source
./compile.sh -c generated.cc -o generated.o
