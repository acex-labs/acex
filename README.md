# ACE-X - Automation & Control Ecosystem

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

ACE-X is an extendable automation and control ecosystem designed for building robust, distributed automation platforms.

## 🚀 Features

- **API-First** - RESTful API for all operations
- **Distributed Execution** - Scale with worker nodes
- **CLI Tools** - Powerful command-line interface
- **Plugin System** - Extend functionality with plugins
- **External datasources with state** - Read external data, stateful

## 📦 Packages

ACE-X is organized as a monorepo with multiple installable packages:

| Package | Description | Installation |
|---------|-------------|--------------|
| [**acex**](./backend/) | Core backend and API | `pip install acex` |
| [**acex-cli**](./cli/) | Command-line interface | `pip install acex-cli` |
| [**acex-worker**](./worker/) | Distributed task worker | `pip install acex-worker` |
| [**acex-mcp-server**](./mcp/) | MCP server for AI assistants | `pip install acex-mcp-server` |

## 🔧 Installation

### Quick Start - Full Installation

```bash
# Install all components
pip install acex acex-cli acex-worker
```

### Minimal Installation

```bash
# Just the core
pip install acex

# Core + CLI
pip install acex-cli  # This includes acex as a dependency

# Core + Worker
pip install acex-worker  # This includes acex as a dependency
```

## 🎯 Quick Example

### Engine Setup

```python
from acex import AutomationEngine

# Initialize the engine
engine = AutomationEngine()

# Database (Postgres)
db = Connection(
    dbname="ace",
    user="postgres",
    password="",
    host="localhost",
    backend="postgresql"
)

# External datasources
netbox = Netbox(
    url="https://netbox.domain.tld/",
    token=os.getenv("NETBOX_TOKEN")
)

ae.add_integration("ipam", netbox)
app = ae.create_app()

# Run the application with uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=80,
    )
    
```

### Configuration as code

#### Static parameters

```python
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Loopback

class LoopbackIf(ConfigMap):
    def compile(self, context):

        lo0 = Loopback(
            index=0,
            name="Lo0",
            description = "MPLS Loopback",
            ipv4 = f"192.0.2.2/24"
        )
        context.configuration.add(lo0)

lo = LoopbackIf()
lo.filters = FilterAttribute("role").eq("core")
```


#### Variable parameters

```python
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Loopback

class LoopbackIf(ConfigMap):
    def compile(self, context):

        lo0 = Loopback(
            index=0,
            name="Lo0",
            description = "MPLS Loopback",
            ipv4 = f"192.0.2.{context.logical_node.id}/24"
        )
        context.configuration.add(lo0)

lo = LoopbackIf()
lo.filters = FilterAttribute("role").eq("core")
```

#### External datasources

```python
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Loopback


class LoopbackIf(ConfigMap):
    def compile(self, context):

        lo0 = Loopback(
            index=0,
            name="Lo0",
            description = "MPLS Loopback",
            ipv4 = context.integrations.ipam.data.ip_addresses({"query_key": "match_value"})
        )
        context.configuration.add(lo0)
lo = LoopbackIf()
lo.filters = FilterAttribute("role").eq("core")
```

### Mapping config to nodes
```python
...

# Instanciate the ConfigMap, makes it discoverable
lo = LoopbackIf()

# Apply filters

## Apply to all nodes with role == core:
lo.filters = FilterAttribute("role").eq("core")

## Apply to all nodes with site == hq:
lo.filters = FilterAttribute("site").eq("hq")

## Apply to all core nodes at site hq:
lo.filters = FilterAttribute("site").eq("hq") && FilterAttribute("role").eq("core")
```


Using the CLI:

# Coming...

## 🏗️ Development

This is a monorepo. Each package can be developed independently:

```bash
# Backend development
cd backend
poetry install
poetry run pytest

# CLI development
cd cli
poetry install

# Worker development
cd worker
poetry install
```

## 🤖 MCP Server

ACE-X includes a Model Context Protocol (MCP) server for integration with AI assistants like Claude Desktop and VS Code Cline:

```bash
# Install the MCP server
pip install acex-mcp-server

# Run the server
acex-mcp
```

See [MCP Server Documentation](./mcp/README.md) for configuration details.

## 📚 Documentation

- [Backend Documentation](./backend/README.md)
- [CLI Documentation](./cli/README.md)
- [Worker Documentation](./worker/README.md)
- [MCP Server Documentation](./mcp/README.md)

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)** - see the [LICENSE](LICENSE) file for details.

### What does AGPL mean?

- ✅ **Free to use** - Use ACE-X for any purpose
- ✅ **Open source** - Full source code available
- ✅ **Modify freely** - Change and adapt as needed
- ⚠️ **Share modifications** - If you modify and run ACE-X as a network service, you must share your modifications
- ⚠️ **Same license** - Derivative works must also be AGPL-licensed

### Dual Licensing

**Commercial licenses** are available for organizations that wish to use ACE-X without the obligations of the AGPL.

For commercial licensing inquiries, contact: **license@acex.dev**

**Why AGPL?**

The AGPL license ensures that improvements to ACE-X benefit the entire community, even when the software is used to provide network services. If you run a modified version of ACE-X as a service, users of that service can request the source code.

## 👤 Author

Johan Lahti <johan.lahti@acebit.se>

## 🔗 Links

- Repository: https://github.com/acex-labs/acex
- Issues: https://github.com/acex-labs/acex/issues