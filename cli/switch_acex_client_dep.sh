#!/bin/bash
# switch_acex_client_dep.sh
# Usage:
#   ./switch_acex_client_dep.sh dev   # för lokal utveckling
#   ./switch_acex_client_dep.sh prod  # för publicering

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
    sed "${SED_INPLACE[@]}" 's|acex-client = ".*"|acex-client = { path = "../client", develop = true }|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-driver-cisco-ioscli = ".*"|acex-driver-cisco-ioscli = { path = "../drivers/cisco_ios_cli", develop = true }|' "$PYPROJECT"
elif [[ "$1" == "prod" ]]; then
    echo "Byter till versionsberoenden (för publicering)"

        # Läs version från varje beroendets egen pyproject.toml
    CLIENT_VERSION=$(grep '^version =' "$(dirname "$0")/../client/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')
    CISCO_IOS_VERSION=$(grep '^version =' "$(dirname "$0")/../drivers/cisco_ios_cli/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')

    sed "${SED_INPLACE[@]}" 's|acex-client = { path = "../client", develop = true }|acex-client = "^'$CLIENT_VERSION'"|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-driver-cisco-ioscli = { path = "../drivers/cisco_ios_cli", develop = true }|acex-driver-cisco-ioscli = "^'$CISCO_IOS_VERSION'"|' "$PYPROJECT"
else
    echo "Använd: $0 dev|prod"
    exit 1
fi
