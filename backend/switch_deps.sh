#!/bin/bash
# switch_deps.sh for backend
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
    sed "${SED_INPLACE[@]}" 's|acex-devkit = ".*"|acex-devkit = { path = "../devkit", develop = true }|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-driver-cisco-ioscli = ".*"|acex-driver-cisco-ioscli = { path = "../drivers/cisco_ios_cli", develop = true }|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-driver-juniper-junoscli = ".*"|acex-driver-juniper-junoscli = { path = "../drivers/juniper_junos_cli", develop = true }|' "$PYPROJECT"
elif [[ "$1" == "prod" ]]; then
    echo "Byter till versionsberoenden (för publicering)"

    # Read major version from the current git tag (unified versioning)
    MAJOR=$(git -C "$(dirname "$0")" describe --tags --exact-match 2>/dev/null | sed 's/^v//' | cut -d. -f1)
    if [[ -z "$MAJOR" ]]; then
        echo "Error: not on an exact git tag. Cannot determine version for prod deps."
        exit 1
    fi

    sed "${SED_INPLACE[@]}" 's|acex-devkit = { path = "../devkit", develop = true }|acex-devkit = "^'$MAJOR'"|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-driver-cisco-ioscli = { path = "../drivers/cisco_ios_cli", develop = true }|acex-driver-cisco-ioscli = "^'$MAJOR'"|' "$PYPROJECT"
    sed "${SED_INPLACE[@]}" 's|acex-driver-juniper-junoscli = { path = "../drivers/juniper_junos_cli", develop = true }|acex-driver-juniper-junoscli = "^'$MAJOR'"|' "$PYPROJECT"
else
    echo "Använd: $0 dev|prod"
    exit 1
fi
