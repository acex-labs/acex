---
kind: added
title: ConfigMaps can be synced from a git repository
audience: admin
---
Instead of mounting a directory, add a repository under `/api/v1/git_repositories`: its HTTPS URL, branch,
the directory that holds the ConfigMaps, and a `token` credential holding a personal access token. The
backend loads the ConfigMaps at once, checks every 30 minutes whether the branch has moved
(`ACEX_GIT_SYNC_POLL_INTERVAL_SECONDS`) and loads them again when it has. `POST
/api/v1/git_repositories/{id}/sync` loads the latest commit now.

A host whose certificate an internal CA signed is trusted by giving the repository the CA chain as
`ca_certificate`.

A commit in which a file fails to import is not loaded: the ConfigMaps already in use stay, and the
repository's `last_error` names the file.

ConfigMaps are code the backend runs, so only users with the `naas-admin` realm role, the same role that
turns on admin mode in the web interface, can see or change repositories. Name another role with
`ACEX_GIT_SYNC_ADMIN_ROLE`. The backend image now includes git.
