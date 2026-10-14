# ACE-X Worker

Runs ACE-X jobs. A worker talks to the backend only through the acex API
(acex-client); it does not import backend code.

## Development

```bash
cd worker
poetry install
poetry run pytest
```

## Running

```bash
ACEX_BASE_URL=http://localhost:8080 \
ACEX_CLIENT_ID=acex-worker \
ACEX_CLIENT_SECRET=... \
poetry run acex-worker
```

At startup the worker logs in to the API with its service account (OIDC
client credentials) and asks `POST /workers/connect` for the broker and the
queues that carry the job types it has code for.

## Configuration

| Env var | |
|---|---|
| `ACEX_BASE_URL` | The acex backend. Default `http://127.0.0.1:8080/`, the backend's dev port. |
| `ACEX_CLIENT_ID` | The worker's OIDC client. Defaults to the backend's client from `/auth/config`. |
| `ACEX_CLIENT_SECRET` | Required when the backend has auth enabled. |
| `ACEX_ISSUER_URL` | Overrides the issuer from `/auth/config`. |
| `ACEX_VERIFY_SSL` | `false` turns off TLS verification. |
