---
kind: added
audience: developer
title: A git repository can belong to one site
---
`GitRepositoryCreate`, `GitRepositoryUpdate` and `GitRepositoryResponse` have a new optional `site`: the ConfigMaps of the repository then apply to the logical nodes of that site only. A blank name means no site, and `null` in an update clears it. A client that does not know the field keeps working.
