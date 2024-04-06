#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -gt 0 ]]; then
	cmd=(c++ -g -lqalculate -Wall -shared -std=c++20 -fPIC "$(python3 -m pybind11 --includes)" "$@")
	echo "${cmd[*]}"
	"${cmd[@]}"
else
	echo "Compiling module"
	"$0" ./module.cc ./options.cc ./generated.o -o qalculate"$(python3-config --extension-suffix)"
	PYTHONPATH=$(pwd):$PYTHONPATH pybind11-stubgen -o . qalculate --enum-class-locations '.*:qalculate'
fi
