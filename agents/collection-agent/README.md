# ACE-X Collection Agent

Collects device data (configurations, LLDP, routes, etc.) via NEDs and uploads to ACE-X.

## Local development

```bash
cd agents/collection-agent
poetry install

ACEX_API_URL=http://localhost/ COLLECTION_AGENT_ID=1 poetry run acex-collection-agent
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ACEX_API_URL` | Yes | ACE-X API base URL (e.g. `http://localhost/` or `https://api.example.com/`) |
| `COLLECTION_AGENT_ID` | Yes | ID of the collection agent to run |
| `ACEX_VERIFY_SSL` | No | Set to `true` to enable SSL verification (default: `false`) |

## Container

```bash
docker run -e ACEX_API_URL=https://api.example.com/ -e COLLECTION_AGENT_ID=1 ghcr.io/acex-labs/acex-collection-agent:latest
```
