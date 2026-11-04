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

Not yet. Authorization is not role based: a valid token gives access to the whole API. Role-based access, with a
read-only role, is planned. Until it exists, treat every token as full access:

- give each integration its own client, so that it can be disabled by itself,
- keep the client secret in a secret store and not in a script,
- keep the lifetime of the token short.

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
