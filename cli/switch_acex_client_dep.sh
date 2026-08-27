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
    sed "${SED_INPLACE[@]}" 's|acex-devkit = ".*"|acex-devkit = { path = "../devkit", develop = true }|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-driver-cisco-ioscli = ".*"|acex-driver-cisco-ioscli = { path = "../drivers/cisco_ios_cli", develop = true }|' "$PYPROJECT"
elif [[ "$1" == "prod" ]]; then
    echo "Byter till versionsberoenden (för publicering)"

    # Read major version from the current git tag (unified versioning)
    MAJOR=$(git -C "$(dirname "$0")" describe --tags --exact-match 2>/dev/null | sed 's/^v//' | cut -d. -f1)
    if [[ -z "$MAJOR" ]]; then
        echo "Error: not on an exact git tag. Cannot determine version for prod deps."
        exit 1
    fi

    sed "${SED_INPLACE[@]}" 's|acex-client = { path = "../client", develop = true }|acex-client = "^'$MAJOR'"|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-devkit = { path = "../devkit", develop = true }|acex-devkit = "^'$MAJOR'"|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-driver-cisco-ioscli = { path = "../drivers/cisco_ios_cli", develop = true }|acex-driver-cisco-ioscli = "^'$MAJOR'"|' "$PYPROJECT"
else
    echo "Använd: $0 dev|prod"
    exit 1
fi
