#!/usr/bin/env bash
# Creates .venv next to this script with the devkit and the kit installed. Run it from anywhere.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3.13}"
"$PYTHON" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ../devkit -e '.[driver,dev]'
echo "ready: .venv/bin/python -m pytest"
