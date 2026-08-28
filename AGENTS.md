# ACEX — Automation Configuration Engine

## What is ACEX?

ACEX is a declarative IaC (Infrastructure as Code) and service orchestration framework for network device configuration. Integrators describe desired network state by composing typed configuration components; the framework handles placement, reference resolution, and serialization into a unified configuration model.

## Core Architecture

### ConfigComponent (base class)
- Path: `backend/src/acex/configuration/components/base_component.py`
- All configuration primitives (HostName, FrontpanelPort, Vlan, StaticRoute, etc.) inherit from `ConfigComponent`
- Each component wraps a Pydantic model with `name`, `type`, and attributes (`AttributeValue` / `ExternalValue`)
- Supports a `pre_init()` hook for preprocessing kwargs before validation

### Configuration (orchestrator)
- Path: `backend/src/acex/configuration/configuration.py`
- Holds a `ComposedConfiguration` instance and a `COMPONENT_MAPPING` dict that maps each component type to a dot-notated path in the composed tree
- Some paths use `string.Template` with variables resolved from the component's own attributes (e.g. `network_instances.${network_instance}.vlans`)
- Key methods:
  - `add(component)` — registers a component, extracts references, sets `attr_ptr` metadata on `ExternalValue` attributes
  - `as_model()` — places all components into `ComposedConfiguration` at their mapped paths, resolves cross-references, returns a complete Pydantic model
  - `to_json()` — serializes the model to a dict

### ComposedConfiguration (target model)
- Path: `devkit/src/acex_devkit/models/composed_configuration.py`
- A nested Pydantic BaseModel defining the full configuration tree:
  - `system.*` — hostname, contact, location, ssh, logging, ntp, snmp, aaa, dhcp, vtp
  - `interfaces` — dict of interface objects keyed by name
  - `network_instances` — dict of VRFs/network instances, each containing `vlans` and `protocols.static_routes`
  - `stp`, `lacp`, `lldp`, `cdp`, `acl`

### Reference System
- `ReferenceTo` — an attribute on component A that points to component B (e.g. SshServer → source_interface)
- `ReferenceFrom` — an external location that points back to this component (e.g. interface → VRF membership)
- `RenderedReference` — intermediate form with `from_ptr` / `to_ptr`
- `Reference` — final resolved pointer stored in the composed model

## Integration Flow (how integrators use the framework)

1. A **ConfigMap** (see `docs/examples/`) defines a `compile()` method
2. `compile()` creates `ConfigComponent` instances and calls `context.configuration.add(component)`
3. `Configuration.as_model()` traverses all registered components, places them in `ComposedConfiguration`, and resolves cross-references
4. The result is a complete, serializable configuration model

This is declarative in the same way as Terraform — the integrator describes *what* should be configured, not the steps to get there.

## Component Categories

| Category | Components | Path prefix |
|---|---|---|
| System | HostName, Contact, Location, DomainName, LoginBanner, MotdBanner | `system.config.*` |
| SSH | SshServer, AuthorizedKey | `system.ssh.*` |
| Logging | LoggingConfig, Console, VtyLine, RemoteServer, FileLogging | `system.logging.*` |
| NTP | NtpServer | `system.ntp.servers` |
| SNMP | SnmpGlobal, SnmpUser, SnmpServer, SnmpTrap, SnmpCommunity | `system.snmp.*` |
| AAA | aaaGlobal, aaaServerGroup, aaaTacacs, aaaRadius, aaaAuthentication/Authorization/AccountingMethods/Events | `system.aaa.*` |
| DHCP | DHCPSnooping, DhcpRelayServer | `system.dhcp.*` |
| Interfaces | FrontpanelPort, ManagementPort, LagInterface, Loopback, Subinterface, Svi | `interfaces` |
| Network Instances | NetworkInstance, L3Vrf | `network_instances` |
| VLAN | Vlan | `network_instances.${ni}.vlans` |
| Routing | StaticRoute, StaticRouteNextHop | `network_instances.${ni}.protocols.static_routes` |
| STP | SpanningTreeGlobal, SpanningTreeRSTP, SpanningTreeMSTP, SpanningTreeMstpInstance, SpanningTreeRapidPVST | `stp.*` |
| ACL | Ipv4Acl, Ipv6Acl, Ipv4AclEntry, Ipv6AclEntry | `acl.*` |
| LACP | LacpConfig | `lacp.config` |
| LLDP | LldpConfig | `lldp` |
| CDP | CdpConfig | `cdp` |
| VTP | Vtp | `system.vtp.config` |

## Project Structure

```
backend/    — Core framework (Configuration, ConfigComponents, drivers)
devkit/     — Shared models (ComposedConfiguration, AttributeValue, ExternalValue)
cli/        — CLI tooling
client/     — Client library
docs/       — Documentation and integration examples (docs/examples/)
drivers/    — Device-specific drivers/translators
mcp/        — MCP server integration
worker/     — Background worker
scripts/    — Utility scripts
```
