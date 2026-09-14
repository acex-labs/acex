# ACE-X

**ACE-X** (Automation & Control Ecosystem) is a declarative platform for network device configuration. Operators describe desired network state by composing typed configuration components — ACE-X handles compilation, diff computation, rendering to vendor CLI, and pushing changes to devices over SSH.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://github.com/acex-labs/acex/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

---

## How it works

1. **Write a ConfigMap** — a Python class that describes one slice of configuration (e.g., "loopback interfaces for all core routers")
2. **Apply filters** — control which devices receive the config via `FilterAttribute` expressions
3. **Compile** — ACE-X resolves external data (NetBox, IPAM) and builds a vendor-agnostic configuration model
4. **Diff & apply** — the CLI shows you the patch commands and sends them over SSH after confirmation
5. **Observe** — collection agents continuously pull running configs from devices and store them for future diffs

This is declarative in the same way as Terraform — describe *what* should be configured, not the steps to get there.

## Packages

ACE-X is organized as a monorepo with multiple installable packages:

| Package | Description | Install |
|---------|-------------|---------|
| [`acex`](https://github.com/acex-labs/acex/tree/main/backend) | Core backend and API | `pip install acex` |
| [`acex-cli`](https://github.com/acex-labs/acex/tree/main/cli) | Command-line interface | `pip install acex-cli` |
| [`acex-worker`](https://github.com/acex-labs/acex/tree/main/worker) | Distributed task worker | `pip install acex-worker` |
| [`acex-mcp-server`](https://github.com/acex-labs/acex/tree/main/mcp) | MCP server for AI assistants | `pip install acex-mcp-server` |

## License

ACE-X is licensed under **AGPL-3.0**. Commercial licenses are available — contact [license@acex.dev](mailto:license@acex.dev).
