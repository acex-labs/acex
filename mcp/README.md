# ACE-X MCP Server

Model Context Protocol (MCP) server for ACE-X, providing AI assistants with access to ACE-X automation and inventory functionality.

## Installation

```bash
pip install acex-mcp-server
```

## Usage

### Running the Server

```bash
acex-mcp
```

### Configuration for Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "acex": {
      "command": "acex-mcp"
    }
  }
}
```

### Configuration for VS Code with Cline

Add to your MCP settings:

```json
{
  "mcpServers": {
    "acex": {
      "command": "acex-mcp",
      "args": []
    }
  }
}
```

## Available Tools

### Automation Tools

- **create_automation** - Create a new automation workflow
- **list_automations** - List all available automations
- **run_automation** - Execute an automation

### Inventory Tools

- **get_asset** - Get information about a specific asset
- **list_assets** - List all assets with optional filtering
- **create_asset** - Create a new asset in the inventory

## Development

```bash
cd mcp
poetry install
poetry run python -m acex_mcp.server
```

## Testing

Test the MCP server using the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector acex-mcp
```

## License

AGPL-3.0 - See [LICENSE](../LICENSE) for details.
