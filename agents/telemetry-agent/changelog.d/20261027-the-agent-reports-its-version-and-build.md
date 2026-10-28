---
kind: added
title: The agent reports its version and build to ACEX
audience: admin
---
Every acknowledgement carries the version of the package, the commit the image was built from and the branch that build ran on, so Settings > About can show what each agent runs. The image takes them from the build arguments `BUILD_ID` and `BUILD_REF` and exposes them as `ACEX_BUILD_ID` and `ACEX_BUILD_REF`; an image built without them reports no build.
