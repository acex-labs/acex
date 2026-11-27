---
kind: added
audience: admin
title: Send a ConfigMap to a git repository as a merge request (GitLab)
---
A git repository can have a merge request token (`merge_request_credential_id`, a `token` credential that holds a GitLab token with the scope `api` and at least the role Developer). `POST /api/v1/git_repositories/{id}/merge_requests` then commits a Python file to a new branch, at the path the caller chooses, and opens a merge request into the branch the repository follows. `GET /api/v1/git_repositories/{id}/tree` lists the directories and files of that branch, to choose the place from. Nothing reaches the followed branch until someone merges on GitLab, and ACEX never merges. The merge request is opened by the token's own user and names the ACEX user who sent it. A path that already holds a file is refused unless `replace` is set, and what GitLab refuses comes back as 502 with GitLab's own words. Needs a database migration (one nullable column). The guide has the steps.
