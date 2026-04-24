# ACE-X Config Agent

Collects device configurations via NEDs and uploads to ACE-X.

## Local development

```bash
cd agents/config-agent
poetry install

ACEX_API_URL=http://localhost/ CONFIG_AGENT_ID=1 poetry run acex-config-agent
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ACEX_API_URL` | Yes | ACE-X API base URL (e.g. `http://localhost/` or `https://api.example.com/`) |
| `CONFIG_AGENT_ID` | Yes | ID of the config agent to run |
| `ACEX_VERIFY_SSL` | No | Set to `true` to enable SSL verification (default: `false`) |

## Container

```bash
docker run -e ACEX_API_URL=https://api.example.com/ -e CONFIG_AGENT_ID=1 ghcr.io/acex-labs/acex-config-agent:latest
```
