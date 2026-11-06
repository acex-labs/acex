---
kind: internal
title: A stable release is compared with its release candidate
---
CI tags the versions a push published as `<package>-<version>` on the commit that published them: release candidates when `dev` is pushed and stable versions when `main` is. The plan of a stable release, and the check on a pull request into the release branch, compare what a package ships (its directory and, for an image, everything its `Dockerfile` copies) with the tag of its newest release candidate, and list what differs apart from the compiled notes, the highlights and the roadmap, the version, `README` files and tests. `changelog.py tag-versions --since <commit>` lists the versions a push changed.
