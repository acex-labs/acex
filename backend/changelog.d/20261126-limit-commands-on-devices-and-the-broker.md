---
kind: security
title: Commands on devices and the broker login can require a role
audience: admin
---
Any token the API accepted could order a command on a device (`POST /api/v1/operations/execute`, `/operations/actions/*`, `/operations/patch/apply`, `/operations/patch/render` and a workflow run), read what the devices answered, stop and delete jobs, and fetch the broker's user and password from `POST /api/v1/workers/connect`. The new setting `ACEX_AUTHZ_OPERATIONS_MODE` limits them to tokens that list a role: `acex-admin` for people, `acex-service` for the workers.

It is a setting of its own and `off` by default, also when `ACEX_AUTHZ_MODE` is `enforce`, so nothing changes after an upgrade. The values are those of `ACEX_AUTHZ_MODE`: `log` lets every request through and logs the callers that `enforce` would refuse (`Would be refused`, once for each caller and route every ten minutes), and `enforce` answers 403 without the role. To switch it on, give the roles as for `ACEX_AUTHZ_MODE`, set `ACEX_AUTHZ_OPERATIONS_MODE=log`, read the log after a round, then set `enforce`.

What each route needs:

- `acex-admin`: ordering runs, patches and workflow runs, changing and deleting workflows, reading runs and their reports, and requeuing, cancelling and deleting jobs.
- `acex-service`: `POST /workers/connect` and a worker's reports on its jobs (`PATCH /workers/jobs/{id}`).
- Either: reading a workflow run and its artifacts, which a worker does to run the next step.

The description of each route in the API reference says which role it needs. The web interface and any script that orders commands need `acex-admin`; the collection agent, the telemetry agent and the Grafana sync use none of these routes. A worker's service account needs `acex-service` before this is enforced. See the API FAQ.
