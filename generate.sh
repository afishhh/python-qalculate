#!/usr/bin/env bash

set -euo pipefail

python3 generate.py
./compile.sh -c generated.cc -o generated.o
