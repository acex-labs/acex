# ACE-X Collection Agent

Collects device data (configurations, LLDP, routes, etc.) via NEDs and uploads to ACE-X.

## Local development

```bash
cd agents/collection-agent
poetry install

ACEX_API_URL=http://localhost/ COLLECTION_AGENT_NAME=default poetry run acex-collection-agent
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ACEX_API_URL` | Yes | ACE-X API base URL (e.g. `http://localhost/` or `https://api.example.com/`) |
| `COLLECTION_AGENT_NAME` | Yes¹ | Name of the collection agent to run. The id is looked up by exact name at startup (retried every 60s until the API answers and the agent exists). |
| `COLLECTION_AGENT_ID` | — | **Deprecated.** Agent id; used only when `COLLECTION_AGENT_NAME` is unset. |
| `ACEX_VERIFY_SSL` | No | Set to `true` to enable SSL verification (default: `false`) |

¹ One of `COLLECTION_AGENT_NAME` or `COLLECTION_AGENT_ID` is required. When both are set the name wins. Agent names are not unique in ACEX; if several agents share the name, the agent logs an error and keeps retrying — rename one or fall back to the id.

## Container

```bash
docker run -e ACEX_API_URL=https://api.example.com/ -e COLLECTION_AGENT_NAME=default ghcr.io/acex-labs/acex-collection-agent:latest
```
