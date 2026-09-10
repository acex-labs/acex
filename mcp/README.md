# ACE-X MCP Server

A Model Context Protocol server that gives AI assistants read-only access to
ACE-X: the network devices it manages, the configuration each is intended to
have, and the configuration snapshots actually collected from them.

It holds no data and no credentials of its own. Every tool is a call to the
ACE-X API made **as the caller**, so the backend authorizes each read against
that user's own permissions.

## Installation

```bash
pip install acex-mcp
```

## Tools

All tools are read-only. Start with `find_nodes` — the `node_id` it returns is
what every other tool takes.

| Tool | What it answers |
|---|---|
| `find_nodes` | Which devices exist, filtered by hostname, site, region, role, vendor, OS or status |
| `get_node` | One device: its identity plus the hardware it runs on |
| `find_assets` | What physical hardware is in inventory, deployed or spare |
| `list_sites` | Which sites exist |
| `list_regions` | Which regions exist, and their sites |
| `get_desired_config` | The configuration ACE-X intends a device to have, rendered as device commands |
| `get_observed_config` | A configuration snapshot collected from a device — latest, at a past moment, or by id |
| `get_running_config` | *Placeholder.* Explains that ACE-X cannot read a device live, and offers the newest snapshot |
| `list_observed_configs` | A device's configuration history |
| `diff_observed_configs` | What changed on a device between two snapshots |
| `get_config_drift` | How a device differs from its intended configuration, compared per component |
| `get_neighbors` | What is physically cabled to a device, per LLDP |

`get_desired_config` and `get_observed_config` take a `section` argument that
keeps only matching configuration blocks, so a question about one interface does
not pull a three-thousand-line config into the model's context.

## Resources and prompts

| Resource | Contents |
|---|---|
| `acex://glossary` | desired vs observed vs running, and what users mean when they say "running config" |
| `acex://entities` | Field-level entity reference, generated from the backend's own models |
| `acex://capabilities` | What this server cannot do |
| `acex://now` | Current UTC time, for resolving "yesterday at 19:00" into a timestamp |

Prompts: `explain_config_change`, `assess_config_risk`,
`assess_config_alignment` — each takes a `diff` and an optional `context`.

## Configuration

Only the backend URL is required. OIDC settings are discovered at startup from
the backend's public `/api/v1/auth/config`, so authentication is configured in
one place — the backend — and never duplicated here.

| Variable | Default | Meaning |
|---|---|---|
| `ACEX_API_URL` | `http://localhost:8080` | Backend base URL, **without** `/api/v1` |
| `ACEX_VERIFY_SSL` | `true` | Verify TLS against the backend and the IdP |
| `ACEX_MCP_TRANSPORT` | `http` | `http` or `stdio` |
| `ACEX_MCP_HOST` | `0.0.0.0` | HTTP bind address |
| `ACEX_MCP_PORT` | `8000` | HTTP port |
| `ACEX_MCP_PATH` | `/mcp` | HTTP path |
| `ACEX_MCP_REQUEST_TIMEOUT` | `60` | Seconds per backend request |
| `ACEX_MCP_MAX_CONFIG_CHARS` | `24000` | Cap on config text per tool call |

## Authentication

The two transports authenticate differently, because only one of them has an
inbound request to take a token from.

**HTTP** — the server verifies the incoming bearer token against the backend's
OIDC issuer, then forwards that same token to the ACE-X API on every tool call.
Inbound verification is not a second layer of protection over the data (the
backend authorizes every read regardless); it is what lets an external client
discover it must log in, makes an expired token fail once at the boundary
instead of becoming a series of tool errors, and identifies the caller in logs.

**stdio** — there is no inbound request, so the process authenticates as the
user through `acex_client`: `ACEX_CLIENT_ID` + `ACEX_CLIENT_SECRET` for a
service identity, or an interactive browser login whose token is cached on disk.

If the backend reports authentication disabled, this server also runs without
it, so a Keycloak-less development stack works.

## Usage

### Running the server

```bash
python3 -m acex_mcp
```

Or via the console script, which does exactly the same thing:

```bash
acex-mcp
```

The Docker Compose stack builds and wires this automatically; the backend
reaches it at `ACEX_AI_MCP_SERVER_URL=http://mcp-server:8000/mcp`.

### Configuration for Claude Desktop

Add to your `claude_desktop_config.json`. `stdio` is required — Claude Desktop
spawns the process and talks to it over a pipe:

```json
{
  "mcpServers": {
    "acex": {
      "command": "acex-mcp",
      "env": {
        "ACEX_MCP_TRANSPORT": "stdio",
        "ACEX_API_URL": "https://acex.example.com"
      }
    }
  }
}
```

### Configuration for VS Code with Cline

Add to your MCP settings, with the same two environment variables:

```json
{
  "mcpServers": {
    "acex": {
      "command": "acex-mcp",
      "args": [],
      "env": {
        "ACEX_MCP_TRANSPORT": "stdio",
        "ACEX_API_URL": "https://acex.example.com"
      }
    }
  }
}
```

## Development

```bash
cd mcp
poetry install
ACEX_API_URL=http://localhost:8080 poetry run python -m acex_mcp
```

## Testing

```bash
poetry run pytest
```

`tests/test_contract.py` guards against the failure that motivated this
rewrite: tools that called endpoints which had moved, and described fields the
API does not return. It checks that every client method the tools call still
exists, and — when a backend is reachable — that every path behind them is
still in its OpenAPI spec.

Interactively, with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector acex-mcp
```

## License

AGPL-3.0 - See [LICENSE](../LICENSE) for details.
