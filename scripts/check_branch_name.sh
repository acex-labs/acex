#!/usr/bin/env bash
# Validates that a branch name follows the project naming convention
# (Conventional Commits style):
#   <prefix>/<description>
#
# Allowed prefixes: feat, fix, chore, docs, refactor, test, hotfix, ci, perf, build
# Description: lowercase letters, digits, hyphens and dots (kebab-case).
#
# Exempt: main, stage and dependabot branches are not validated.
#
# Usage:
#   scripts/check_branch_name.sh              # validates the current branch
#   scripts/check_branch_name.sh <name>       # validates the given name
#
# Exit code 0 = OK, 1 = invalid name.

set -euo pipefail

ALLOWED_PREFIXES="feat|fix|chore|docs|refactor|test|hotfix|ci|perf|build"
PATTERN="^(${ALLOWED_PREFIXES})/[a-z0-9][a-z0-9._-]*$"

# Branches that should not be validated
is_exempt() {
    local branch="$1"
    case "$branch" in
        main|stage) return 0 ;;
        dependabot/*) return 0 ;;
        *) return 1 ;;
    esac
}

branch_name="${1:-}"

if [ -z "$branch_name" ]; then
    branch_name="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
fi

# HEAD (detached) or empty — nothing to validate
if [ -z "$branch_name" ] || [ "$branch_name" = "HEAD" ]; then
    exit 0
fi

if is_exempt "$branch_name"; then
    exit 0
fi

if [[ "$branch_name" =~ $PATTERN ]]; then
    exit 0
fi

# --- Invalid name: build a specific, helpful error message -------------------

RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Split into prefix (before the first '/') and the rest, if a '/' exists
prefix=""
description=""
if [[ "$branch_name" == */* ]]; then
    prefix="${branch_name%%/*}"
    description="${branch_name#*/}"
fi

# Suggest the correct prefix for common mistakes (e.g. feature -> feat)
suggest_prefix() {
    case "$1" in
        feature)        echo "feat" ;;
        bug|bugfix)     echo "fix" ;;
        doc)            echo "docs" ;;
        tests)          echo "test" ;;
        *)              echo "" ;;
    esac
}

reason=""
suggestion=""
if [ -z "$prefix" ]; then
    reason="missing prefix — the name must start with '<prefix>/'"
elif [[ ! "$prefix" =~ ^(${ALLOWED_PREFIXES})$ ]]; then
    reason="'${prefix}/' is not an allowed prefix"
    suggested="$(suggest_prefix "$prefix")"
    if [ -n "$suggested" ] && [ -n "$description" ]; then
        suggestion="did you mean '${suggested}/${description}'?"
    fi
elif [[ ! "$description" =~ ^[a-z0-9][a-z0-9._-]*$ ]]; then
    if [ -z "$description" ]; then
        reason="missing description after '${prefix}/'"
    else
        reason="the description '${description}' contains invalid characters (use lowercase letters, digits and hyphens)"
    fi
fi

echo -e "${RED}✗ Invalid branch name: '${branch_name}' — ${reason}.${NC}" >&2
if [ -n "$suggestion" ]; then
    echo -e "${YELLOW}  Hint: ${suggestion}${NC}" >&2
fi
echo "" >&2
echo "Branch names must follow the format: <prefix>/<description>" >&2
echo "" >&2
echo "Allowed prefixes: feat, fix, chore, docs, refactor, test, hotfix, ci, perf, build" >&2
echo "Description: lowercase letters, digits and hyphens (kebab-case), e.g:" >&2
echo "  feat/add-ntp-support" >&2
echo "  fix/static-route-nil-check" >&2
echo "  hotfix/1.2.1-crash-on-boot" >&2
echo "" >&2
echo "Rename the current branch with:" >&2
echo "  git branch -m <new-name>" >&2
exit 1
