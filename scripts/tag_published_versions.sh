#!/usr/bin/env bash
# Tag the versions a push published, <package>-<version>, on the commit that published them.
# A stable release is compared with the tag of its release candidate, so a tag has to stay where it was put.
#
# Only what the pushed branch publishes is tagged (see branch_publishes_version.sh): release candidates on dev
# and stable versions on main. A stable version that reaches dev is published by the merge into main, and that
# commit gets the tag.
#
# Usage: scripts/tag_published_versions.sh <branch> <commit before the push> <pushed commit>

set -euo pipefail

branch="${1:?branch}"
before="${2:-}"
sha="${3:?pushed commit}"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here/.."

if [ -z "$before" ] || [ "$before" = "0000000000000000000000000000000000000000" ]; then
    echo "There is no commit before this push, so there is nothing to compare with."
    exit 0
fi
if ! git rev-parse --verify --quiet "${before}^{commit}" > /dev/null; then
    echo "::error::${before} is not in this clone (a force push?), so what this push published cannot be told." \
        "Tag the versions it published by hand: git tag <package>-<version> ${sha}"
    exit 1
fi

tags="$(python "$here/changelog.py" tag-versions --since "$before")"

failed=0
for tag in $tags; do
    version="${tag##*-}"
    if ! "$here/branch_publishes_version.sh" "$branch" "$version"; then
        echo "$tag is not published from $branch"
        continue
    fi
    if git rev-parse --verify --quiet "refs/tags/${tag}^{commit}" > /dev/null; then
        if [ "$(git rev-list -n 1 "$tag")" = "$sha" ]; then
            echo "$tag is already on this commit"
        else
            echo "::error::$tag already exists on $(git rev-list -n 1 "$tag"), not on $sha"
            failed=1
        fi
        continue
    fi
    git tag "$tag" "$sha"
    git push origin "refs/tags/$tag"
    echo "tagged $tag"
done
exit "$failed"
