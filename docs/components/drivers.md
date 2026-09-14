# Drivers (NEDs)

A NED (Network Element Driver) is a Python package that translates between ACE-X's vendor-agnostic configuration model and a specific device OS. Each driver implements four roles: render, render_patch, transport, and parse.

## Built-in drivers

| Driver | Package | OS |
|--------|---------|-----|
| Cisco IOS CLI | `acex-driver-cisco-ioscli` | Cisco IOS / IOS XE |
| Juniper JunOS CLI | `acex-driver-juniper-junoscli` | Juniper JunOS |

## How drivers are loaded

Drivers are discovered at startup via the `acex.neds` setuptools entry point group:

```toml
# In a driver's pyproject.toml
[project.entry-points."acex.neds"]
cisco-ios-cli = "acex_driver_cisco_ioscli:CiscoIOSCLIDriver"
```

The `NEDManager` scans all installed packages for this entry point and registers the drivers. Collection agents download any missing drivers from the backend's `/api/v1/neds/download/{filename}` endpoint and install them via pip at startup.

## Driver roles

### Renderer — `render(config, asset) -> str`

Converts a `ComposedConfiguration` (vendor-agnostic Pydantic model) into a vendor-specific config string.

For Cisco IOS, this involves:

1. Resolving abstract interface indices to real hardware port names (e.g., `GigabitEthernet1/0/1`) by looking up the device's hardware model YAML
2. Handling stacked switches (asset clusters) — distributing interfaces across stack members
3. Resolving cross-references (e.g., VRF membership onto interfaces, SSH source interface)
4. Grouping VTY lines into ranges
5. Rendering a Jinja2 template that walks the configuration tree

### Patch renderer — `render_patch(diff, node_instance) -> str`

Converts a computed diff into a minimal set of patch commands. Uses a `GeneratorRegistry` that maps change paths (e.g., `("system", "config")`, `("interfaces", "*")`) to command generator functions.

### Transport — `get_config` / `send_config`

Opens SSH connections to network devices using Scrapli/asyncssh.

- `get_config(node, connection)` — runs `show running-config` and returns the raw text
- `send_config(node, connection, commands)` — sends a list of CLI commands
- `get_lldp_neighbors(node, connection)` — runs `show lldp neighbors detail` and `show cdp neighbors detail`, parses the output, returns a neighbor list for topology mapping

### Parser — `parse(raw_config: str) -> ComposedConfiguration`

Parses raw CLI output (from `show running-config`) back into the vendor-agnostic model using TextFSM templates. This is what enables the intent-diff workflow — both desired and observed configs are represented as the same structured model, so diffing is deterministic.

## Writing a custom driver

Subclass `RendererBase`, `TransportBase`, and `ParserBase` from `acex.plugins.neds.core.base_driver`, implement the abstract methods, and register your class via the `acex.neds` entry point.
