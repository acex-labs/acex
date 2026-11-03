---
kind: added
title: Drivers built on the mapper render configuration patches
---
`Mapper.render_patch` renders a diff as the lines that take the device from observed to desired: added and changed components from the desired render, removed ones negated from the observed render. `Diff.scoped(path, prune)` narrows a diff to a path. A diff now holds the trees it was made from, so `Codec.render_patch` gets everything it needs from it.
