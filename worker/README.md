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

## NVD API key

The worker fetches the optional NVD key from the backend once per discovery job.
Without a key, it uses NVD's lower request rate. The worker does not read
`NVD_API_KEY` from its environment.

Manage the key with an authenticated `acex-client`:

```python
from acex_devkit.models.cve import CveApiKeyUpdate

client.cves.api_key.update(payload=CveApiKeyUpdate(api_key=nvd_api_key))  # Save or replace
key = client.cves.api_key.get()  # None if not configured
client.cves.api_key.delete()  # Remove
```

The same operations are available through `PUT`, `GET`, and `DELETE` at
`/api/v1/cves/api_key`. For `PUT`, send `{"api_key": "<nvd-api-key>"}`.

The backend stores the key encrypted using `ACEX_CREDENTIALS_ENCRYPTION_KEY`.
Keep that encryption key stable across restarts and replicas. Any authenticated
caller can manage or retrieve the NVD key. Use HTTPS outside local development;
dev mode disables authentication.
