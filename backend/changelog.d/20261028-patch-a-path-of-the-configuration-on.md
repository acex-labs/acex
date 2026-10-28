---
kind: added
title: Patch a path of the configuration on selected nodes, from a reviewed plan
---
`POST /api/v1/operations/patch/render` reads each node live and renders the patch that brings its configuration at a path, such as `system.ntp.servers`, to the desired state; nothing is sent. With `prune`, what the device holds there that the desired configuration doesn't declare is removed too. `POST /api/v1/operations/patch/apply` sends the plan's patches to the nodes you choose from it: each node is read again and patched only if it still renders the planned patch, then read once more to verify. Plans and applies are runs like the others, listed with `kind=patch`.
