# ACE-X Client

Synchronous Python client for the ACE-X backend.

## Installation

```bash
pip install acex-client
```

## Quick start

```python
from acex_client import Acex

with Acex(base_url="https://acex.local") as client:
    result = client.inventory.sites.query(name="stockholm")
    for site in result:
        print(site.id, site.name)
```

Auth is auto-detected from `/auth/config`. Override via env vars:

- `ACEX_BASE_URL` — backend URL
- `ACEX_ISSUER_URL`, `ACEX_CLIENT_ID`, `ACEX_CLIENT_SECRET` — OIDC override
- `ACEX_VERIFY_SSL=false` — disable TLS verification

or inject an `AuthProvider` directly:

```python
from acex_client.auth import ClientCredentialsAuth

auth = ClientCredentialsAuth(client_id="...", client_secret="...", issuer_url="...", verify_ssl=True)
with Acex(base_url="...", auth=auth) as client:
    ...
```

## Namespaces

| Namespace | Resources / actions |
|---|---|
| `client.inventory` | `sites`, `regions`, `region_assignments`, `contacts`, `contact_assignments`, `assets`, `asset_clusters`, `collection_agents`, `credentials`, `logical_nodes`, `management_connections`, `node_instances`, `node_credentials(node_id)`, `site_credentials(site_name)` |
| `client.observability` | `agents` (with bound `outputs`, `rules`, `nodes`), `grafana` |
| `client.operations` | `compliance` (`.check()`, `.site()`), `config_history.list_changes()`, `lldp` (`.upload()`, `.topology()`, `.by_site()`, `.get()`, `.reverse()`) |
| `client.config_components` | `catalog()`, `generate()`, `reconcile()`, `drivers()`, `translate()` |
| `client.neds` | `list()`, `get()`, `download()` |
| `client.ai` | `ask()`, `analyze()` (SSE-streamed) — `None` if backend has no `ai_ops` mounted |
| `client.system` | `auth_config()`, `health_node()`, `health_site()` |

## CRUD pattern

Each resource inherits the mixins for the verbs it supports. All mutations
return a `LiveInstance` proxy that holds the Pydantic model; `.save()` diffs
against the original and PATCHes only changed fields, `.delete()` removes
the resource:

```python
site = client.inventory.sites.create(name="stockholm", city="SE")
site.display_name = "Stockholm HQ"
site.save()  # PATCH /inventory/sites/{id} with {display_name: ...}
site.delete()  # DELETE /inventory/sites/{id}
```

`get`, `update`, `create`, `delete` all raise `AcexNotFoundError` on HTTP 404
rather than returning `None` — wrap in `try/except` for "if exists" flows.

## Actions and sub-resources

Action methods use `@action(method, path_template)`:

```python
client.inventory.collection_agents.manifest(id=1)
client.inventory.collection_agents.ack(id=1, payload=CollectionAgentAck(config_revision=5))
```

Bound sub-resources are accessed via `.parent_or_id`:

```python
client.inventory.collection_agents.rules(1).create(region="eu")
client.observability.agents.outputs(agent_id).list()
```

Via a `LiveInstance`, the bound sub-resource is exposed as an attribute:

```python
agent = client.observability.agents.get(1)
agent.outputs.create(influxdb_version="v2", url="http://influx:8086")
```

## Errors

```python
from acex_client import (
    AcexNotFoundError,
    AcexValidationError,
    AcexAuthError,
    AcexPermissionError,
    AcexServerError,
    AcexTimeoutError,
    AcexConnectionError,
)
```

All errors inherit from `AcexError`. HTTP errors carry `status_code` and
`body` attributes.

## Examples

See `examples/crud.py` and `examples/observe.py`.
