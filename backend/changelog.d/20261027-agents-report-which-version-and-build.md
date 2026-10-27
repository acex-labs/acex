---
kind: added
title: Agents report which version and build they run
---
Collection and telemetry agents now send the version of their package, the commit their image was built from and the branch that build ran on (`dev` for development images) with every acknowledgement. The API stores them and returns them as `agent_version`, `build_id` and `build_ref` on each agent, and `/api/v1/health/about` returns `build_ref` next to `build_id`. An agent that is too old to report them shows none until it is updated; an agent that stops reporting after a rollback shows none as well.
