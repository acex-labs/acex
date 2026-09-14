# MCP Server

The `acex-mcp-server` package exposes ACE-X inventory data as [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) tools, making ACE-X a data source that AI assistants can query when answering questions about the network.

## Install and run

```bash
pip install acex-mcp-server

# Set the backend URL and start
ACEX_API_URL=http://localhost:8080 acex-mcp
```

The server listens on port 8000 by default.

## Connecting to an AI assistant

=== "Claude Desktop"

    Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

    ```json
    {
      "mcpServers": {
        "acex": {
          "command": "acex-mcp",
          "env": {
            "ACEX_API_URL": "http://localhost:8080"
          }
        }
      }
    }
    ```

=== "VS Code (Cline)"

    Add to your Cline MCP settings:

    ```json
    {
      "acex": {
        "command": "acex-mcp",
        "env": {
          "ACEX_API_URL": "http://localhost:8080"
        }
      }
    }
    ```

## Available tools

| Tool | Description |
|------|-------------|
| `list_assets` | List physical hardware (filter by vendor, OS, model, serial, assigned status) |
| `list_logical_nodes` | List config templates (filter by role, site, sequence, hostname, assigned) |
| `get_specific_logical_node` | Full desired config for one logical node |
| `list_node_instances` | List deployed node instances (filter by site, hostname, status, etc.) |
| `get_node_instance` | A node instance with its vendor-specific compiled config |
| `get_node_instance_config` | Latest observed (running) config for a node instance |

## Available resources

The MCP server also exposes two documentation resources that AI assistants can read for context:

- `acex://docs/system-architecture` — explanation of Assets, Logical Nodes, and Node Instances
- `acex://docs/workflow-examples` — common workflow examples

## Use within AI Ops

The MCP server is also used internally by ACE-X's own AI Ops `ask()` feature. When an operator asks the AI assistant a question, the backend connects to its own MCP server as a client, giving the model live tool access to the current inventory and running configs.
