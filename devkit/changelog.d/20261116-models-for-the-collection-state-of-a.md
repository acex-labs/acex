---
kind: added
title: Models for the collection state of a node
---
A collection agent reports what it found for each node with `CollectionResult` (`node_id`, `ok`, a `CollectionFailure` category and a message of at most 500 characters), sent as a `CollectionResultsUpload`. `NodeCollectionStateResponse` says whether a node is `ok` or `failing`, when it was last tried and last collected, since when it has failed, how many times in a row, why, and which collection agent made the last attempt (`agent_id` and `agent_name`). It is on `NodeListItem` and `NodeInstance` as `collection`, empty until an agent has reported on the node. `AgentCollectionSummary` counts the nodes an agent made the last attempt on: `collected`, `not_collected` and `by_category`.
