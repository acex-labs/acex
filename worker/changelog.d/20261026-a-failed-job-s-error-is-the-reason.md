---
kind: changed
title: A failed job's error is the reason, without the handler's name
---
Before, a job's error read like `Handler HandleExecute for job 212 (acex.operations.execute) raised '...'`. Now it
is just the reason, for example `Node 4 has no primary management connection with an IP`. An unexpected error
keeps its type in front, for example `KeyError: 'x'`. Which handler raised it, and where, is still in the
worker's log.
