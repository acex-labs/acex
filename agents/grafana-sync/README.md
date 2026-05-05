# ACE-X Grafana Sync

Reconciles a target Grafana instance from the ACE-X observability API. Fetches
the generated datasource and dashboard definitions and pushes them via the
Grafana REST API. Datasources are created if missing (manual edits are
preserved); dashboards are upserted on every cycle (intent is the source of
truth) and optionally pruned when removed from ACE-X.

## How it works

On each poll cycle the agent fetches the full desired state (datasources +
dashboards) from ACE-X and computes a SHA-256 digest. If the digest matches
the last successful reconcile, the cycle is a no-op — no writes are sent to
Grafana. When the digest changes (or the previous reconcile failed), it:

1. Ensures the target folder (default uid `acex`, title `ACEX`) exists in
   Grafana via `GET /api/folders/{uid}` + `POST /api/folders`.
2. For each ACE-X datasource, checks Grafana with `GET /api/datasources/uid/{uid}`
   and creates via `POST /api/datasources` if missing. Existing datasources are
   never overwritten — manual edits (e.g. rotated credentials) are preserved.
3. For each ACE-X dashboard, looks up `GET /api/dashboards/uid/{uid}`. If the
   dashboard already lives in a different folder, the agent refuses to touch
   it. Otherwise upserts via `POST /api/dashboards/db` with `overwrite: true`
   into the target folder.
4. If `PRUNE_DASHBOARDS=true`, deletes any dashboard inside the target folder
   whose uid no longer appears in the ACE-X listing. Dashboards outside the
   folder are never touched.

UIDs from ACE-X are deterministic, so re-runs are idempotent.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ACEX_API_URL` | Yes | — | ACE-X API base URL |
| `GRAFANA_URL` | Yes | — | Target Grafana base URL |
| `GRAFANA_TOKEN` | One of | — | Grafana service account / API token (Bearer auth) |
| `GRAFANA_USER` + `GRAFANA_PASSWORD` | One of | — | Grafana credentials (Basic auth) — alternative to `GRAFANA_TOKEN` |
| `GRAFANA_FOLDER_UID` | No | `acex` | Folder uid to reconcile dashboards into |
| `GRAFANA_FOLDER_TITLE` | No | `ACEX` | Folder title used when creating |
| `POLL_INTERVAL_SECONDS` | No | `60` | Reconcile loop interval |
| `PRUNE_DASHBOARDS` | No | `true` | Delete dashboards in folder not present in ACE-X |
| `ACEX_VERIFY_SSL` | No | `false` | Verify TLS for the ACE-X API |
| `GRAFANA_VERIFY_SSL` | No | `true` | Verify TLS for the Grafana API |

The Grafana token needs at least: folder create, datasource create,
dashboard write, and (if pruning) dashboard delete permissions on the target
folder. A service account with `Editor` role plus folder admin works.

## Local development

```bash
cd agents/grafana-sync
poetry install

ACEX_API_URL=http://localhost/ \
GRAFANA_URL=http://localhost:3000 \
GRAFANA_TOKEN=glsa_xxx \
poetry run acex-grafana-sync
```

## Container

```bash
docker run \
  -e ACEX_API_URL=https://api.example.com/ \
  -e GRAFANA_URL=https://grafana.example.com \
  -e GRAFANA_TOKEN=glsa_xxx \
  ghcr.io/acex-labs/acex-grafana-sync:latest
```
