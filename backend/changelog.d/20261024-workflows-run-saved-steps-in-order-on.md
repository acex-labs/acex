---
kind: added
title: Workflows run steps on a graph, each on its own nodes
---
A workflow is a graph from start to end under `/api/v1/operations/workflows`. Each box is a step with its own nodes:

- execute: raw commands
- action: an abstract action run from the node, such as ping
- probe: a ping from ACEX itself, to the nodes' management IPs or to an address
- compute: values computed from earlier artifacts
- assert: checks that must hold, or the run fails
- condition: chooses the edges of its true or false side
- wait: waits without holding a worker

Each step names the artifacts it leaves as expressions over its own `result`, for example
`version = regex(result.output, "Version (\S+)")`. Later steps read them by name: `show interface {iface}` or
`percent(reachable) >= 95`. Expressions are a fixed language, not code.

Edges may branch, rejoin and loop back. A step waits for every branch into it that can still finish, and a
step that fails stops the run. A step that runs more often than the workflow's `max_rounds` (100 by default)
fails the run too.

A workflow is saved as it is drawn. Its `check` lists what keeps it from running, warns about loops with no way
out or no wait, and lists the artifacts each step can read. `POST /api/v1/operations/workflows/check` checks a
graph without saving it.

`POST /api/v1/operations/workflows/{id}/runs` starts a run in one of three modes:

- `run` goes to the end.
- `evaluate` pauses after each step until it is continued.
- `dry_run` reaches no device and shows what each step would send.

Runs can be stopped, and finished runs deleted with everything they produced. Workflow runs are not listed
among bulk runs.
