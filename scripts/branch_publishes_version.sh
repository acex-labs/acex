#!/usr/bin/env bash
# Exit 0 if a push to <branch> publishes <version>, 1 otherwise.
# main publishes stable versions, dev publishes release candidates (X.Y.ZrcN).
#
# Usage: scripts/branch_publishes_version.sh <branch> <version>

set -euo pipefail

branch="${1:?branch}"
version="${2:?version}"

case "${branch}:${version}" in
    main:*rc*) exit 1 ;;
    main:*) exit 0 ;;
    dev:*rc*) exit 0 ;;
    *) exit 1 ;;
esac
