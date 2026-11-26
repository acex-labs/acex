# Integrations

ACE-X integrates with several external systems. Each integration has a specific direction and purpose.

## NetBox / IPAM

**Direction:** Read-only (ACE-X queries NetBox; never writes back)

Used as an inventory source and for live data lookups in `compile()` methods.

```python
from acex.plugins.integrations.netbox import Netbox

netbox = Netbox(url="https://netbox.example.com/", token=os.getenv("NETBOX_TOKEN"))
ae.add_integration("ipam", netbox)
```

In a ConfigMap:

```python
class LoopbackIf(ConfigMap):
    def compile(self, context):
        ip = context.integrations.ipam.data.ip_addresses({"device": context.logical_node.hostname})
        lo0 = Loopback(index=0, name="Lo0", ipv4=ip)
        context.configuration.add(lo0)
```

NetBox can also be used as the inventory backend to populate Assets and Logical Nodes automatically (replacing the built-in database backend for inventory).

## HashiCorp Vault

**Direction:** Read-only (ACE-X reads secrets; never writes to Vault)

Used to store SSH credentials and SNMP secrets for network devices. Supports both token auth and AppRole.

```bash
ACEX_CREDENTIALS_VAULT_ADDR=https://vault.example.com
ACEX_CREDENTIALS_VAULT_TOKEN=...
# or AppRole:
ACEX_CREDENTIALS_VAULT_ROLE_ID=...
ACEX_CREDENTIALS_VAULT_SECRET_ID=...
# or, in Kubernetes, the service account of the pod (no secret to store):
ACEX_CREDENTIALS_VAULT_K8S_ROLE=acex
ACEX_CREDENTIALS_VAULT_K8S_MOUNT=kubernetes          # where the Kubernetes auth method is mounted (default)
ACEX_CREDENTIALS_VAULT_K8S_TOKEN_PATH=/var/run/secrets/kubernetes.io/serviceaccount/token   # default
# the certificate check: true (default), false, or the path of the CA file Vault's certificate is checked against:
ACEX_CREDENTIALS_VAULT_VERIFY=true
```

If more than one way to log in is set, the AppRole is used before Kubernetes and Kubernetes before the token. With an
AppRole or Kubernetes the backend logs in again when its Vault token has expired, so a credential with source `vault`
keeps working for as long as the role can log in; the service account token file is read again at every login, since
Kubernetes rotates it. A static token is not renewed: when it expires the credentials read from Vault fail until the
token is replaced and the backend restarted.

A CA file given in `ACEX_CREDENTIALS_VAULT_VERIFY` is used for Vault only. Nothing else the backend calls over HTTPS,
such as the OIDC provider, is affected by it.

If Vault is not configured, credentials are stored encrypted in PostgreSQL using a symmetric key (`ACEX_CREDENTIALS_ENCRYPTION_KEY`).

## Keycloak

**Direction:** ACE-X calls Keycloak to validate tokens; Keycloak never calls ACE-X

All API requests are authenticated via JWT (RS256). At startup ACE-X fetches the JWKS from the Keycloak discovery endpoint and caches it. Agents (collection-agent, telemetry-agent, grafana-sync) also authenticate to the backend using Keycloak client credentials.

```bash
ACEX_ISSUER_URL=http://keycloak:8180/realms/acex
# For agents:
ACEX_CLIENT_ID=collection-agent
ACEX_CLIENT_SECRET=...
```

## InfluxDB

**Direction:** Write-only (device metrics flow into InfluxDB; ACE-X does not read from InfluxDB)

ACE-X generates Telegraf configuration files containing InfluxDB output blocks. Telegraf — managed by the telemetry agent — performs the actual writes. Supports InfluxDB v1, v2, and v3 (Cloud Dedicated / IOx).

```python
ae.observability(
    influxdb=InfluxDBv2(
        url="https://influxdb.example.com",
        org="my-org",
        bucket="network-metrics",
        token=os.getenv("INFLUXDB_TOKEN"),
    )
)
```

## Grafana

**Direction:** ACE-X generates desired state → grafana-sync reads it and reconciles with Grafana's API

ACE-X generates datasource and dashboard JSON from the observability configuration. The grafana-sync agent polls ACE-X every 60 seconds, computes a diff, and applies changes to Grafana via its HTTP API. Dashboards that ACE-X no longer defines are pruned from the managed folder (if `prune_dashboards=True`).

## AI Providers (OpenAI-compatible)

**Direction:** Two-way — ACE-X sends prompts, providers stream completions back

Used by the AI Ops feature. Any OpenAI-compatible endpoint is supported (Groq, OpenRouter, Ollama, local models), over Chat Completions or OpenAI's Responses API, including Azure OpenAI signed in with Entra ID. Configure named providers and per-task failover chains:

```bash
ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL=https://api.groq.com/openai/v1
ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY=gsk_...
ACEX_AI_OPS_PROVIDERS__LOCAL__BASE_URL=http://localhost:11434/v1
ACEX_AI_OPS_PROVIDERS__LOCAL__API_KEY=ollama
ACEX_AI_OPS_PROVIDERS__LOCAL__MODELS=qwen3:32b
ACEX_AI_OPS_CHAINS__DEFAULT="groq/llama-3.3-70b-versatile, local/qwen3:32b"
ACEX_AI_OPS_CHAINS__ANALYSIS="groq/deepseek-r1"
```

See [AI Ops](../examples/ai_ops.md) for full configuration details.

## Bug reporting (ADO / Slack)

**Direction:** One-way outbound (ACE-X posts to ADO or Slack)

When a user submits a bug report via the web UI, ACE-X can create an Azure DevOps work item or post a Slack message.

```bash
# Azure DevOps
ACEX_BUG_REPORT_ADO_SERVICE_PAT=...
ACEX_BUG_REPORT_ADO_ORG=my-org
ACEX_BUG_REPORT_ADO_PROJECT=my-project
ACEX_BUG_REPORT_ADO_FEATURE_ID=123

# Slack
ACEX_BUG_REPORT_SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```
