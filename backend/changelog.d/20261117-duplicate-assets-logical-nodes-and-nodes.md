---
kind: changed
title: Duplicate assets, logical nodes and nodes are refused
---
Adding or editing an asset with a serial number that another asset already has is now refused. The same goes for a logical node with a hostname that already exists, for a second node on a logical node that already has one, and for a second node on an asset or cluster that already backs a node. Serial numbers and hostnames are compared ignoring capital letters and spaces around them, and a blank one is refused. The API answers 409 and names the existing record, so a client can point the user at it.

Adding a node for a logical node or asset that does not exist, or moving a node onto one, is now answered with 404.

If your database already holds duplicates, including nodes that share an asset, the backend still starts. It writes them to the startup log, with the statement to run once they are sorted out, and leaves that unique index out until then. New duplicates are refused either way.
