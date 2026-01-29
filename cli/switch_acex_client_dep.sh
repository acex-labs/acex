#!/bin/bash
# switch_acex_client_dep.sh
# Usage:
#   ./switch_acex_client_dep.sh dev   # för lokal utveckling
#   ./switch_acex_client_dep.sh prod  # för publicering

set -e

PYPROJECT="$(dirname "$0")/pyproject.toml"

if [[ "$1" == "dev" ]]; then
    echo "Byter till path-beroende (lokal utveckling)"
    sed -i '' 's|acex-client = ".*"|acex-client = { path = "../client", develop = true }|' "$PYPROJECT"
elif [[ "$1" == "prod" ]]; then
    echo "Byter till versionsberoende (för publicering)"
    # Ange rätt version nedan
    VERSION=$(grep '^version =' "$PYPROJECT" | head -1 | sed 's/.*"\(.*\)".*/\1/')
    sed -i '' 's|acex-client = { path = "../client", develop = true }|acex-client = "^'$VERSION'"|' "$PYPROJECT"
else
    echo "Använd: $0 dev|prod"
    exit 1
fi
