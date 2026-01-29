#!/bin/bash
# switch_acex_client_dep.sh
# Usage:
#   ./switch_acex_client_dep.sh dev   # för lokal utveckling
#   ./switch_acex_client_dep.sh prod  # för publicering

set -e

elif [[ "$1" == "prod" ]]; then

PYPROJECT="$(dirname "$0")/pyproject.toml"

# Välj rätt sed-flagga för macOS (BSD) eller Linux (GNU)
if sed --version >/dev/null 2>&1; then
    SED_INPLACE=(-i)
else
    SED_INPLACE=(-i '')
fi

if [[ "$1" == "dev" ]]; then
    echo "Byter till path-beroende (lokal utveckling)"
    sed "${SED_INPLACE[@]}" 's|acex-client = ".*"|acex-client = { path = "../client", develop = true }|' "$PYPROJECT"
elif [[ "$1" == "prod" ]]; then
    echo "Byter till versionsberoende (för publicering)"
    VERSION=$(grep '^version =' "$PYPROJECT" | head -1 | sed 's/.*"\(.*\)".*/\1/')
    sed "${SED_INPLACE[@]}" 's|acex-client = { path = "../client", develop = true }|acex-client = "^'$VERSION'"|' "$PYPROJECT"
else
    echo "Använd: $0 dev|prod"
    exit 1
fi
