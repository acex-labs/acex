---
kind: added
title: Models for the git repositories that ConfigMaps are synced from
audience: developer
---
The backend syncs ConfigMaps from a git repository through `GitRepositoryCreate`, `GitRepositoryUpdate` and `GitRepositoryResponse`, with `GitAuthMethod` (`https_anonymous`, `https_token`) and `GIT_AUTH_CREDENTIAL_TYPES`, which says which type of credential each method signs in with. A URL must be https:// and hold no user name or password, the directory of the ConfigMaps must lie inside the repository, and a CA certificate must be PEM.
