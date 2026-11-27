---
kind: added
audience: developer
title: Models for sending a file to a git repository as a merge request
---
`GitRepositoryCreate`, `GitRepositoryUpdate` and `GitRepositoryResponse` have a new optional `merge_request_credential_id`: the id of a `token` credential that merge requests are sent with. `null` in an update clears it. New models: `MergeRequestCreate` (`path`, `content`, `title`, `description`, `replace`; the path must be a `.py` file inside the repository), `MergeRequestResponse` (`url`, `number`, `source_branch`, `target_branch`, `path`) and `GitRepositoryTree` (`branch`, `directories`, `files`, `truncated`). A client that does not know the field keeps working.
