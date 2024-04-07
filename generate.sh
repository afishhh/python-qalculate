#!/usr/bin/env bash

set -euo pipefail

if hash nix 2>/dev/null; then
	nix build .#libqalculate.src --out-link "$1"
else
	git clone "https://github.com/Qalculate/libqalculate" "$1"
fi

PYTHONPATH="$PYTHONPATH:." python3 -m generate "$@"
