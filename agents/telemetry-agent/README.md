# ACE-X Telemetry Agent

Sidecar that polls the ACE-X observability API and keeps `telegraf.conf` in
sync with the central configuration. Designed to run alongside Telegraf in
the same pod, sharing a config volume.

## How it works

1. Polls `GET /api/v1/observability/agents/{id}` every 60s.
2. When `config_revision` changes (or on first run), fetches
   `GET /api/v1/observability/agents/{id}/config` and atomically writes it
   to `TELEGRAF_CONFIG_PATH`.
3. Acks the revision with `POST /api/v1/observability/agents/{id}/ack`.

Telegraf is expected to pick up the new file on its own (e.g. via SIGHUP
sent by another sidecar, or a `--watch-config` Telegraf flag).

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ACEX_API_URL` | Yes | — | ACE-X API base URL |
| `TELEMETRY_AGENT_NAME` | Yes¹ | — | Name of the telemetry agent. The id is looked up by exact name at startup (retried every `POLL_INTERVAL_SECONDS` until the API answers and the agent exists). |
| `TELEMETRY_AGENT_ID` | — | — | **Deprecated.** Agent id; used only when `TELEMETRY_AGENT_NAME` is unset. |
| `TELEGRAF_CONFIG_PATH` | No | `/etc/telegraf/telegraf.conf` | Where to write the rendered config |
| `POLL_INTERVAL_SECONDS` | No | `60` | Manifest poll interval |
| `ACEX_VERIFY_SSL` | No | `false` | Set to `true` to enable SSL verification |

¹ One of `TELEMETRY_AGENT_NAME` or `TELEMETRY_AGENT_ID` is required. When both are set the name wins. Agent names are not unique in ACEX; if several agents share the name, the agent logs an error and keeps retrying — rename one or fall back to the id.

## Local development

```bash
cd agents/telemetry-agent
poetry install

ACEX_API_URL=http://localhost/ \
TELEMETRY_AGENT_NAME=default \
TELEGRAF_CONFIG_PATH=/tmp/telegraf.conf \
poetry run acex-telemetry-agent
```

## Container

```bash
docker run \
  -e ACEX_API_URL=https://api.example.com/ \
  -e TELEMETRY_AGENT_NAME=default \
  -v telegraf-config:/etc/telegraf \
  ghcr.io/acex-labs/acex-telemetry-agent:latest
```
