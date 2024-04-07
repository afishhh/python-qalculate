#!/usr/bin/env bash

set -euo pipefail

export PYTHONPATH="$1:$PYTHONPATH"
pybind11-stubgen -o "$1" qalculate --enum-class-locations '.*:qalculate'
