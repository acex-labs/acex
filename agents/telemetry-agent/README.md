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
| `TELEMETRY_AGENT_ID` | Yes | — | Telemetry agent ID |
| `TELEGRAF_CONFIG_PATH` | No | `/etc/telegraf/telegraf.conf` | Where to write the rendered config |
| `POLL_INTERVAL_SECONDS` | No | `60` | Manifest poll interval |
| `ACEX_VERIFY_SSL` | No | `false` | Set to `true` to enable SSL verification |

## Local development

```bash
cd agents/telemetry-agent
poetry install

ACEX_API_URL=http://localhost/ \
TELEMETRY_AGENT_ID=1 \
TELEGRAF_CONFIG_PATH=/tmp/telegraf.conf \
poetry run acex-telemetry-agent
```

## Container

```bash
docker run \
  -e ACEX_API_URL=https://api.example.com/ \
  -e TELEMETRY_AGENT_ID=1 \
  -v telegraf-config:/etc/telegraf \
  ghcr.io/acex-labs/acex-telemetry-agent:latest
```
