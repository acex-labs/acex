#!/usr/bin/env bash
# Blocks commits of env-files (.env, .env.<variant>, *.env, .envrc) — these
# may contain secrets and must never end up in the repository.
#
# Note: an env-file that is already tracked in git triggers when it is
# staged/modified. Remove it from git (keep it locally) with:
#   git rm --cached <file>
#
# Usage (pre-commit passes staged files as arguments):
#   scripts/check_no_env_files.sh <file1> <file2> ...
#
# Exit code 0 = OK, 1 = env-file among the files.

set -euo pipefail

RED='\033[0;31m'
NC='\033[0m'

if [ $# -eq 0 ]; then
    exit 0
fi

violations=()

for f in "$@"; do
    # Ta bort raderade filer ur kontrollen (avtrackning ska inte blockeras)
    [ -f "$f" ] || continue

    base="${f##*/}"

    # Templates (.env.example, dev.env.example etc.) only contain
    # placeholder values and are allowed.
    case "$base" in
        *.example) continue ;;
    esac

    case "$base" in
        .env|.env.*|*.env|.envrc)
            violations+=("$f") ;;
    esac
done

if [ ${#violations[@]} -eq 0 ]; then
    exit 0
fi

echo -e "${RED}✗ Env-files may not be committed — they can contain secrets:${NC}" >&2
for f in "${violations[@]}"; do
    echo "  $f" >&2
done
echo "" >&2
echo "Fix:" >&2
echo "  git rm --cached <fil>   # untrack (behåller filen lokalt) + commit" >&2
echo "" >&2
echo "Håll värdena lokalt i filen och versionera templates som *.env.example." >&2
exit 1
