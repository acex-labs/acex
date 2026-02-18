# ACE-X AI Coding Agent Instructions

## Project Overview

ACE-X is a network automation ecosystem using a monorepo structure with Poetry for dependency management. It provides **Configuration-as-Code** for network devices through an extensible plugin architecture with external datasource integration (Netbox, SQLite, etc.).

### Core Architecture

**Monorepo Structure** with independent packages:
- `backend/` - Core automation engine (`acex`) - FastAPI REST API
- `cli/` - CLI tool (`acex-cli`) - Typer-based command interface
- `worker/` - Distributed task execution (`acex-worker`) - Optional Celery integration
- `devkit/` - Driver/plugin development kit (`acex-devkit`) - Base classes for extending
- `mcp/` - Model Context Protocol server for AI assistant integration
- `drivers/` - Network element drivers (Cisco IOS, Juniper, etc.)

**Key Component Relationships:**
```
AutomationEngine (backend/src/acex/automation_engine/)
├── PluginManager - Manages integration plugins
├── Inventory - Assets & logical nodes (from plugins or DB)
├── ConfigCompiler - Compiles ConfigMaps to device configs
├── DeviceConfigManager - Manages device configurations
└── Integrations - External datasources (Netbox, IPAM, etc.)
```

## Development Workflows

### Environment Setup

**CRITICAL:** Use `./scripts/dev-setup.sh` for initial setup. This:
- Configures Poetry with `virtualenvs.in-project = true`
- Creates `.venv/` in each package directory
- Installs all packages in editable mode with cross-dependencies

**Activating environments (Poetry 2.0+):**
```bash
cd backend  # or cli, worker, mcp, devkit
source $(poetry env info --path)/bin/activate
```

**Switch dependencies for development/publishing:**
```bash
# In backend/, cli/, or client/ directories:
./switch_deps.sh dev   # Use path dependencies for local dev
./switch_deps.sh prod  # Use version dependencies for publishing
```

### Making Code Changes

All packages are installed in **editable mode** - changes to `src/` directories are immediately available without reinstalling. Just restart Python processes or reimport modules.

### Testing

Each package has independent tests (though test files may not exist yet):
```bash
cd backend
poetry run pytest
```

## Configuration-as-Code Pattern

### ConfigMap Pattern

**ConfigMaps** are the primary abstraction for defining device configurations. They compile to device-specific configs using the `ConfigCompiler`.

**Basic structure:**
```python
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Loopback

class LoopbackIf(ConfigMap):
    def compile(self, context):
        # context provides: logical_node, configuration, integrations
        lo0 = Loopback(
            index=0,
            name="Lo0",
            description="MPLS Loopback",
            ipv4=f"192.0.2.{context.logical_node.id}/24"
        )
        context.configuration.add(lo0)

# Instantiate and apply filters
lo = LoopbackIf()
lo.filters = FilterAttribute("role").eq("core")
```

**Key points:**
- `compile()` method receives a `ConfigMapContext` with access to node data and integrations
- Use `context.configuration.add()` to add configuration components
- Filters use `FilterAttribute` for node selection (role, site, etc.)
- ConfigMaps are discoverable by being instantiated at module level
- ConfigMap directories are registered via `ae.add_configmap_dir("config_maps")`

### Using External Datasources in ConfigMaps

**External datasources** (Netbox, custom APIs) are accessed via `context.integrations`:

```python
class LoopbackIf(ConfigMap):
    def compile(self, context):
        # Query external datasource - returns ExternalValue
        ipv4 = context.integrations.ipam.data.ip_addresses({"device_id": context.logical_node.id})
        
        lo0 = Loopback(
            index=0,
            name="Lo0",
            ipv4=ipv4  # ExternalValue resolved by ConfigCompiler
        )
        context.configuration.add(lo0)
```

**Integration registration in app:**
```python
from acex.plugins.integrations import Netbox

netbox = Netbox(
    url="https://netbox.example.com/",
    token=os.getenv("NETBOX_TOKEN"),
    verify_ssl=False
)

ae = AutomationEngine(db_connection=db)
ae.add_integration("ipam", netbox)  # Access via context.integrations.ipam
```

### Configuration Components

Located in `backend/src/acex/configuration/components/`:
- Base: `base_component.py` - `ConfigComponent` class with Pydantic validation
- Interfaces: `interfaces/` - `Loopback`, `FrontpanelPort`, `ManagementPort`, `Svi`, `LagInterface`
- Network Instances: `network_instances/` - `Vlan`, `L3Vrf`
- System: `system/` - AAA, SNMP, SSH configs
- Other: `lacp/`, `spanning_tree/`, `vlan/`

**All components:**
- Inherit from `ConfigComponent`
- Define `model_cls` for Pydantic validation
- Auto-generate unique names for mapping in composite configurations
- Support `ExternalValue` for deferred datasource resolution

## Plugin Architecture

### Integration Plugin Pattern

**Factory Pattern** for external datasources:
```python
# In acex.plugins.integrations
class Netbox(IntegrationPluginFactoryBase):
    def __init__(self, url: str, token: str, verify_ssl: bool = True):
        self.base_url = f"{url}api/"
        self.rest = RestClient(self.base_url, verify_ssl=verify_ssl)
    
    def create_plugin(self, type: str|None = None) -> 'NetboxPlugin':
        return NetboxPlugin(self.rest, type)

class NetboxPlugin(IntegrationPluginBase):
    # Implements: query(), get(), create(), update(), delete()
    DATA_TYPES = ["ip_addresses", "devices", "prefixes"]
    RESOURCE_TYPES = ["ip_addresses"]  # Stateful resources
```

**Plugin types:**
- **Asset plugins** - Provide device/asset inventory
- **Logical node plugins** - Provide logical network nodes
- **Generic datasource plugins** - External data (IPAM, CMDB, etc.)

### Network Element Driver Pattern

**Located in:** `devkit/src/acex_devkit/drivers/base.py`

Drivers combine three components:
```python
from acex_devkit.drivers import NetworkElementDriver, TransportBase, RendererBase, ParserBase

class MyDriver(NetworkElementDriver):
    renderer_class = MyRenderer   # Converts models to device CLI/XML
    transport_class = MyTransport # Handles device connection & push
    parser_class = MyParser       # Parses device config to models
```

**Driver discovery:** Place drivers in `drivers/` directory with proper naming.

## Project Conventions

### Module Imports
- Use **lazy imports** in `AutomationEngine.__init__()` to avoid circular dependencies
- Backend imports devkit: `from acex_devkit.models import ...`
- ConfigMaps import components: `from acex.configuration.components.interfaces import ...`

### File Organization
- ConfigMaps go in project-specific `config_maps/` directory (see `docs/examples/`)
- Drivers are separate packages in `drivers/` with own `pyproject.toml`
- Each package has `src/{package_name}/` structure

### Naming Conventions
- ConfigMap classes: PascalCase (e.g., `LoopbackIf`)
- Component classes: PascalCase matching their function (e.g., `Loopback`, `FrontpanelPort`)
- Plugin factory classes: PascalCase (e.g., `Netbox`, `Sqlite`)
- Package names: lowercase with hyphens (e.g., `acex-devkit`)

### Version Management
- Versions are defined in each package's `pyproject.toml`
- Also update `__init__.py` with `__version__`
- Use `switch_deps.sh` to sync inter-package version dependencies

## Application Bootstrap

**Standard application setup:**
```python
from acex import AutomationEngine
from acex.database import Connection
from acex.plugins.integrations import Netbox

# Database connection
db = Connection(
    dbname="ace",
    user="postgres",
    password="",
    host="localhost",
    backend="postgresql"
)

# Create engine
ae = AutomationEngine(
    db_connection=db,
    assets_plugin=netbox,        # Optional: external inventory
    logical_nodes_plugin=netbox  # Optional: external nodes
)

# Add integrations for ConfigMaps
ae.add_integration("ipam", netbox)

# Add ConfigMap directory
ae.add_configmap_dir("config_maps")

# AI Operations (optional)
ae.ai_ops(
    enabled=True,
    base_url=os.getenv("ACEX_AI_API_BASEURL"),
    api_key=os.getenv("ACEX_AI_API_KEY"),
    mcp_server_url=os.getenv("ACEX_MCP_URL")
)

# CORS for API
ae.add_cors_allowed_origin("*")

# Create FastAPI app
app = ae.create_app()

# Run with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
```

## Key Files

- **Architecture:** [backend/src/acex/automation_engine/automationengine.py](backend/src/acex/automation_engine/automationengine.py) - Main engine orchestration
- **ConfigMap:** [backend/src/acex/config_map/config_map.py](backend/src/acex/config_map/config_map.py) - Base ConfigMap class
- **Components:** [backend/src/acex/configuration/components/base_component.py](backend/src/acex/configuration/components/base_component.py) - Base config component
- **Drivers:** [devkit/src/acex_devkit/drivers/base.py](devkit/src/acex_devkit/drivers/base.py) - Driver base classes
- **Examples:** [docs/examples/](docs/examples/) - Full working examples (example1-example10)
- **Setup:** [scripts/dev-setup.sh](scripts/dev-setup.sh) - Development environment setup
- **Dev Guide:** [DEVELOPMENT.md](DEVELOPMENT.md) - Development workflows

## Important Context

- **AGPL-3.0 License** - Network service modifications must be shared
- **Python 3.13+** required
- **Poetry** is the only supported package manager
- Database support: PostgreSQL (primary), SQLite (dev/testing)
- CLI uses **Typer** with dynamic command discovery from `cli/src/acex_cli/commands/`
- MCP server enables AI assistant integration (Claude Desktop, VS Code)
