#!/bin/bash
# switch_deps.sh
# Usage:
#   ./switch_deps.sh dev   # för lokal utveckling
#   ./switch_deps.sh prod  # för publicering

set -e



PYPROJECT="$(dirname "$0")/pyproject.toml"

# Välj rätt sed-flagga för macOS (BSD) eller Linux (GNU)
if sed --version >/dev/null 2>&1; then
    SED_INPLACE=(-i)
else
    SED_INPLACE=(-i '')
fi

if [[ "$1" == "dev" ]]; then
    echo "Byter till path-beroenden (lokal utveckling)"
    sed "${SED_INPLACE[@]}" 's|acex = ".*"|acex = { path = "../../backend", develop = true }|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-devkit = ".*"|acex-devkit = { path = "../../devkit", develop = true }|' "$PYPROJECT"
elif [[ "$1" == "prod" ]]; then
    echo "Byter till versionsberoenden (för publicering)"

    # Läs version från varje beroendets egen pyproject.toml
    ACEX_VERSION=$(grep '^version =' "$(dirname "$0")/../backend/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')
    DEVKIT_VERSION=$(grep '^version =' "$(dirname "$0")/../devkit/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')

    sed "${SED_INPLACE[@]}" 's|acex = { path = "../../backend", develop = true }|acex = "^'$ACEX_VERSION'"|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-devkit = { path = "../../devkit", develop = true }|acex-devkit = "^'$DEVKIT_VERSION'"|' "$PYPROJECT"
else
    echo "Använd: $0 dev|prod"
    exit 1
fi
