---
kind: added
audience: admin
title: A git host can sync a repository at once with a webhook
---
A git repository can have a webhook secret (`webhook_credential_id`, a `token` credential). GitLab or GitHub then calls `POST /api/v1/git_repositories/{id}/webhook` on every push, with the secret as `X-Gitlab-Token` or as the signature `X-Hub-Signature-256`, and a push to the branch the repository follows syncs it in the background, instead of at the next check (every 30 minutes). The call needs no login, only the secret; a wrong secret answers 401, a repository without a webhook 404, and a ping, another branch, a tag or another event 200 without doing anything. Needs a database migration (one nullable column). The guide has the steps for GitLab and GitHub.
