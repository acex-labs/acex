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
    echo "Switching to path dependencies (local development)"
    sed "${SED_INPLACE[@]}" 's|acex-client = ".*"|acex-client = { path = "../../client", develop = true }|' "$PYPROJECT"
elif [[ "$1" == "prod" ]]; then
    echo "Switching to versioned dependencies (for publishing)"
    CLIENT_VERSION=$(grep '^version =' "$(dirname "$0")/../../client/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')
    sed "${SED_INPLACE[@]}" 's|acex-client = { path = "../../client", develop = true }|acex-client = "^'$CLIENT_VERSION'"|' "$PYPROJECT"
else
    echo "Usage: $0 dev|prod"
    exit 1
fi
