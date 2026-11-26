---
kind: added
audience: developer
title: A git repository can have a webhook secret
---
`GitRepositoryCreate`, `GitRepositoryUpdate` and `GitRepositoryResponse` have a new optional `webhook_credential_id`: the id of a `token` credential whose token is the secret of the repository's webhook. `null` in an update clears it. A client that does not know the field keeps working.
