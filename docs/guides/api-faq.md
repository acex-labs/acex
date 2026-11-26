# API access: questions and answers

How to call the ACEX API from a script or another system, and how to read the inventory. The examples use two
placeholders: `ISSUER` is the OIDC realm of your installation and `API` is the address of the API.

```bash
ISSUER=https://keycloak.example.com/realms/acex
API=https://acex.example.com
```

## Authentication

### How do I authenticate?

Send an access token from your identity provider in the `Authorization` header:

```bash
curl -s "$API/api/v1/inventory/node_instances" -H "Authorization: Bearer $TOKEN"
```

The API accepts a JWT signed with RS256, issued by the configured issuer (`ACEX_OIDC_ISSUER_URL`), with the audience
`acex` (`ACEX_OIDC_AUDIENCE`). The OpenAPI document and the Swagger page need no token.

### How do I get a token for a script or another system?

Give the system its own client in the realm, so that it can be disabled without touching anyone else. In Keycloak:

1. Create a client with **Client authentication** on and **Service accounts roles** on.
2. Add an **Audience** mapper to it that adds the client `acex` to the access token. Without it the API answers
   `Invalid audience`.
3. Copy the client secret from the **Credentials** tab and keep it in your secret store.

Then ask for a token with the client credentials grant:

```bash
curl -s -X POST "$ISSUER/protocol/openid-connect/token" \
  -d grant_type=client_credentials -d client_id=<CLIENT_ID> -d client_secret=<CLIENT_SECRET>
```

The answer holds `access_token` and `expires_in`, the lifetime in seconds. There is no refresh token: ask again when
the token has expired.

### How do I get a token with my own account?

Use the device authorization grant. It works for any user of the realm, and needs no secret. Turn it on once for the
client you log in with (Keycloak: the client, Settings, **OAuth 2.0 Device Authorization Grant**). Then:

```bash
curl -s -X POST "$ISSUER/protocol/openid-connect/auth/device" -d client_id=acex
```

The answer holds `user_code`, `verification_uri` and `device_code`. Open the address in a browser, log in and enter the
code. Then fetch the token. While you have not finished the login the answer is `authorization_pending`, so ask again
every `interval` seconds:

```bash
curl -s -X POST "$ISSUER/protocol/openid-connect/token" \
  -d grant_type=urn:ietf:params:oauth:grant-type:device_code -d client_id=acex -d device_code=<DEVICE_CODE>
```

The answer holds an `access_token` and a `refresh_token`. Get a new access token with:

```bash
curl -s -X POST "$ISSUER/protocol/openid-connect/token" \
  -d grant_type=refresh_token -d client_id=acex -d refresh_token=<REFRESH_TOKEN>
```

The session ends when it has been idle for too long or has reached its maximum age, and then you log in again. Both are
set in the realm. A login by a person is for trying things out. A system that runs by itself should have a client.

### Why does `username` and `password` in curl not work?

The password grant is off for the client of the web interface, and the answer is `Client not allowed for direct access
grants`. Use the device authorization grant above.

### Why do I get 401?

The `detail` in the answer says why:

| `detail` | Cause | Do this |
|---|---|---|
| `Not authenticated` | There is no `Authorization: Bearer ...` header, or it is malformed | Send the header |
| `Token has expired` | The token is too old. A copied token usually is | Ask for a new one |
| `Invalid audience — expected 'acex'` | The token has no audience `acex` | Add an Audience mapper to the client |
| `Invalid issuer — expected '...'` | The token comes from another realm or another address of the realm than the one the API trusts | Ask the issuer address the API names |
| `Invalid token signature` | The token is not from the issuer, or is cut off | Check that the whole token was copied |

A 503 with `Identity provider unavailable` means the API cannot reach the issuer to check the signature. Try again.

### How long does a token last, and how is it renewed and revoked?

The identity provider decides the lifetime: read `expires_in` in the answer (the realm that comes with the Docker Compose
setup uses one hour). The API checks the signature and the claims itself and does not ask the provider whether a token
has been revoked. Disabling a client or a user, or changing a secret, therefore stops new tokens at once but a token
that is already issued works until it expires.

### Which permissions are needed? Can I have a read-only account?

A valid token gives access to the whole API, with two exceptions that can be limited to tokens that list a role:
reading a device login in the clear, and the routes that run commands on devices, read what they answered and hand out
the broker's login to a worker (see the two questions below). There is no read-only role yet, so treat every other
token as full access:

- give each integration its own client, so that it can be disabled by itself,
- keep the client secret in a secret store and not in a script,
- keep the lifetime of the token short.

### Who may read a device login in the clear?

`ACEX_AUTHZ_MODE` decides, and it is `off` until it is changed, so nothing is refused after an upgrade:

| `ACEX_AUTHZ_MODE` | A token without the role |
|---|---|
| `off` | gets the login, as before |
| `log` | gets the login, and the API logs who would have been refused (once for each caller and route every ten minutes) |
| `enforce` | is refused with 403 |

The roles are `acex-admin`, for people who read a login in the web interface, and `acex-service`, for the collection
agent and the worker, which fetch logins to do their work (`ACEX_AUTHZ_ADMIN_ROLE` and `ACEX_AUTHZ_SERVICE_ROLE` rename
them). The API reads them from the token at `realm_access.roles` and at `resource_access.<audience>.roles`, which is
where Keycloak puts the realm roles and the roles of the client `acex`. `ACEX_AUTHZ_ROLES_CLAIMS` takes other dotted
paths, comma-separated, for another identity provider (for example `roles` or `groups`).

The realm of the Docker Compose setup (`keycloak/realm-export.json`) has both roles: `acex-admin` for the user `admin` and
`acex-service` for the service account of the client `acex-agents`. A realm that was imported before they were added keeps
its old roles, since Keycloak imports a realm only once.

To roll it out in Keycloak:

1. Create the realm roles `acex-admin` and `acex-service`.
2. Give `acex-service` to the service account of each client that fetches logins (the collection agent and the worker:
   the client, **Service accounts roles**, **Assign role**). Give `acex-admin` to the people who may read a login.
3. Check that a token lists them: `realm_access.roles` in the decoded access token. The API reads the access token, not
   the ID token that the web interface reads for its own checks. A client that does not have full scope (Keycloak: the
   client, **Client scopes**, **Full scope allowed** off) gets a realm role in its token only after a scope mapping
   for that role, so add one for each such client.
4. Set `ACEX_AUTHZ_MODE=log`, let the agents run a round, and read the log. A `Would be refused` line names the caller
   (the client or the user) that still lacks a role.
5. When it stays quiet, set `ACEX_AUTHZ_MODE=enforce`.

### Who may run commands on devices, and read what they answered?

The routes that put commands or configuration on devices, the reports of what the devices answered, and the one that
hands the broker's login to a worker have their own setting, `ACEX_AUTHZ_OPERATIONS_MODE`. It takes the same three
values as `ACEX_AUTHZ_MODE` and is `off` until it is changed, whatever `ACEX_AUTHZ_MODE` says, so nothing is refused
after an upgrade and each group of routes can be switched on in its own time.

| `ACEX_AUTHZ_OPERATIONS_MODE` | A token without the role |
|---|---|
| `off` | is let through, as before |
| `log` | is let through, and the API logs who would have been refused (once for each caller and route every ten minutes) |
| `enforce` | is refused with 403 |

Which role each route needs (the names are those of `ACEX_AUTHZ_ADMIN_ROLE` and `ACEX_AUTHZ_SERVICE_ROLE`; each
route's description in the API reference says it too):

| Routes | Role |
|---|---|
| `POST /api/v1/operations/execute`, `/operations/actions/*`, `/operations/patch/render`, `/operations/patch/apply` | `acex-admin` |
| `GET /api/v1/operations/runs`, `/operations/runs/{id}`, `/operations/runs/{id}/report` | `acex-admin` |
| `POST`, `PATCH` and `DELETE` of a workflow under `/api/v1/operations/workflows`, and `POST /operations/workflows/{id}/runs` | `acex-admin` |
| `GET /api/v1/operations/workflows/runs` and `.../runs/{id}/steps/{job_id}`; `POST .../runs/{id}/continue` and `.../stop`; `DELETE .../runs/{id}` | `acex-admin` |
| `GET /api/v1/operations/workflows/runs/{id}` and `.../runs/{id}/artifacts` | `acex-admin` or `acex-service` (a worker reads them to run the next step) |
| `GET /api/v1/workers/jobs`, `GET /workers/jobs/{id}`, `POST .../requeue`, `POST .../cancel`, `DELETE /workers/jobs` and `DELETE /workers/jobs/{id}` | `acex-admin` |
| `POST /api/v1/workers/connect` and `PATCH /workers/jobs/{id}` | `acex-service` |

The routes that only describe things and reach no device stay open to every valid token: `GET /operations/patch/tree`,
`GET /workers/job_types`, `POST /operations/workflows/check` and reading a saved workflow. A role of the admin is not
a role of a worker: a person does not need the broker's login, and a worker does not order commands.

The web interface calls the routes of the first rows when someone orders a run or opens Operations, so the people who
use it need `acex-admin` once this is enforced. The collection agent, the telemetry agent and the Grafana sync use none
of these routes.

To roll it out, give the roles as in the steps above (the service account of the worker is a client of its own, with
`acex-service`), then:

1. Set `ACEX_AUTHZ_OPERATIONS_MODE=log`, let people and workers do what they do for a round, and read the log. A
   `Would be refused` line that names `ACEX_AUTHZ_OPERATIONS_MODE` is a caller that still lacks a role.
2. When it stays quiet, set `ACEX_AUTHZ_OPERATIONS_MODE=enforce`.
3. Start workers only after this: until then any valid token of the installation can order commands once a worker is
   connected.

### Why do I get 403?

The token is valid but does not list a role the route needs, and the setting of that route's group
(`ACEX_AUTHZ_MODE` or `ACEX_AUTHZ_OPERATIONS_MODE`) is `enforce`. The `detail` names the roles. Ask for one of them for
your user or client.

## Inventory data

### How are nodes, hardware and management connections related?

A node (`node_instance`) ties them together:

- the **logical node** has the hostname, role, site and regions,
- the **asset** is the hardware: vendor, serial number, hardware model, OS and OS version. `asset_ref_type` says whether
  `asset_ref_id` points at one asset or at an asset cluster,
- the **management connections** say how to reach it: `target_ip`, `connection_type` (`ssh` or `telnet`) and `primary`.

References to credentials are shown as `id`, `name` and `credential_type` only.

| Endpoint | Returns |
|---|---|
| `GET /api/v1/inventory/node_instances` | a page of nodes with hostname, site, role, vendor, OS and management connections |
| `GET /api/v1/inventory/node_instances/{id}` | one node with its asset, logical node and management connections |
| `GET /api/v1/inventory/assets` | the hardware |
| `GET /api/v1/inventory/management_connections` | the connections |
| `GET /api/v1/inventory/logical_nodes` | the logical nodes |

An example, with made up values, from `GET /api/v1/inventory/node_instances/42`:

```json
{
  "id": 42,
  "admin_status": "active",
  "provision_status": "provisioned",
  "asset_ref_id": 17,
  "asset_ref_type": "asset",
  "asset": {
    "id": 17,
    "type": "asset",
    "vendor": "cisco",
    "os": "cisco_iosxe",
    "hardware_model": "C9300-48P",
    "serial_number": "FOC0000XXXX",
    "os_version": "17.9.4"
  },
  "logical_node": {"id": 9, "hostname": "sw-example-01", "role": "access", "site": "SITE-A", "regions": ["EMEA"]},
  "management_connections": [
    {"id": 31, "node_id": 42, "primary": true, "connection_type": "ssh", "target_ip": "192.0.2.10"}
  ],
  "credentials": [{"id": 3, "name": "network-read", "credential_type": "ssh"}],
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-02T00:00:00Z"
}
```

### Which id identifies a node for good?

The `id` of the node (`node_instance`). The hostname is on the logical node, the address is on the management
connection and the hardware is pointed out by `asset_ref_id`, so the node keeps its `id` when any of them changes.

### Which management address should I use?

The connection with `primary: true`. A node's connections are returned with the primary one first. The address is
`target_ip`.

## Synchronisation

### How do I list and filter nodes?

`GET /api/v1/inventory/node_instances` takes these filters: `site`, `region`, `hostname`, `management_connection_ip`,
`role`, `vendor`, `os`, `admin_status`, `provision_status`, `logical_node_id` and `asset_ref_id`. `sort` (`id`,
`hostname`, `site`, `role`, `admin_status`, `provision_status`, `ip` or `ned_id`) and `order` (`asc` or `desc`) order
the answer, and `limit` (100 unless you ask for another) and `offset` page through it. The answer is:

```json
{"items": [], "total": 0, "limit": 100, "offset": 0}
```

### Can I fetch only what changed since the last synchronisation?

Not with a filter. Each node has `created_at` and `updated_at`. Fetch the list and compare `updated_at` with what you
stored last time.

### How are decommissioned and deleted nodes shown?

A decommissioned node stays in the list with `admin_status` `decommissioned`. Filter on `admin_status` to include or
leave it out. A node that is deleted (`DELETE`) is gone, with its management connections, so a node that was in your
last list and is not in this one has been deleted.

### Are there limits on page size or request rate?

None is enforced for nodes: `limit` is 100 unless you ask for more, and there is no cap or rate limit in the API. Choose a
page size that suits you, a few hundred is fine, and page with `offset` until you have `total` items.

## Where is the reference?

Every endpoint, parameter and response is in the OpenAPI document at `$API/api/v1/openapi.json`, and as a page you can
try things on at `$API/api/v1/docs`.
