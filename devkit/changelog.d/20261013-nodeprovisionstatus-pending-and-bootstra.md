---
kind: changed
title: NodeProvisionStatus: `pending` and `bootstrapping` replaced by `enrolled`
audience: developer
breaking: true
refs: #312, #314
---
The `NodeProvisionStatus` values `pending` and `bootstrapping` are removed and `enrolled` is added (a node in ZTP waiting to be discovered, approved and provisioned). Code that compares against, or sends, the removed values must use `enrolled`; the ZTP stage within `enrolled` now comes from the asset (`ZtpStage`). This is also a change to the backend and client API.
