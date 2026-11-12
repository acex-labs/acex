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

### Keeping a driver and the process that runs it in step

Agents and workers install their drivers from the backend, so they can meet a driver that was written for another version of the contract between a driver and the process that runs it. That contract is the **NED interface**: a number that devkit defines (`acex_devkit.drivers.NED_INTERFACE`) and raises only when the contract changes in a way that breaks either side.

A driver declares the interface it was written for as a number in its class body:

```python
class CiscoIOSCLIDriver(NetworkElementDriver):
    interface_version = 2
```

Write the number, not `NED_INTERFACE`. The declaration says what the driver was written for, and a reference would follow whichever devkit the driver happens to be loaded under. When devkit raises `NED_INTERFACE`, a test fails for each driver in this repository until it has been ported and declares the new number. The backend lists the declared number for each driver as `interface_version` in `GET /api/v1/neds`. A driver that declares none is listed with `null` and is not checked.

An agent or worker names the interfaces it can run. A driver that declares another one is not installed and not used. The process says why in its log, and what needs the driver fails with the reason, for example:

```text
NED 'CiscoIOSCLIDriver' not loaded: CiscoIOSCLIDriver v5.0.0 implements NED interface 3, this process runs 2: update this agent or worker
```

If an agent already has a driver for that NED it keeps using it and only logs the reason. If it has none, every node that needs the NED reports the reason, and the agent tries those nodes again every five minutes, so a driver that is fixed from the outside is picked up without waiting for the next full collection. A worker, which must render what the backend publishes, fails the job with the reason. When the backend serves a driver that is older than the process runs, the message says to update the API instead. A driver whose code cannot be loaded in the process, for example because a dependency is missing, is not used either, and the reason is reported the same way.

Nothing is held against a driver that declares no interface, which is what every driver served by a backend from before the number looks like, or against a process that names no interfaces. When devkit raises `NED_INTERFACE`, the collection agent and the worker have to be changed to run the new interface (`SUPPORTED_NED_INTERFACES`). Their tests fail until they are.

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

Subclass `NetworkElementDriver` from `acex_devkit.drivers`, give it the `codec_class` and `transport_class` that do the work (and, where it has them, a `state_class` and an `actions_class`), list the `platforms` it supports, and register the class via the `acex.neds` entry point. Declare the `interface_version` it was written for, as described [above](#keeping-a-driver-and-the-process-that-runs-it-in-step): agents and workers cannot tell whether they can run a driver that does not.
