# Config Maps

A ConfigMap is the primary unit of configuration authoring in ACE-X. Each ConfigMap describes one slice of network device configuration and is applied to any device that matches its filters.

## Structure

```python
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Loopback


class LoopbackIf(ConfigMap):
    def compile(self, context):
        # Add components to context.configuration
        lo0 = Loopback(index=0, name="Lo0", ipv4="192.0.2.1/32")
        context.configuration.add(lo0)


# Instantiate — this makes the ConfigMap discoverable
lo = LoopbackIf()
lo.filters = FilterAttribute("role").eq("core")
```

The `compile(context)` method receives a `CompileContext` with:

| Attribute | What it is |
|-----------|------------|
| `context.logical_node` | The logical node being compiled (id, hostname, role, site, etc.) |
| `context.configuration` | The `Configuration` instance — call `.add(component)` to register components |
| `context.integrations` | Registered plugins (e.g., `context.integrations.ipam`) |

## Static parameters

Parameters that are the same for every device:

```python
class NtpConfig(ConfigMap):
    def compile(self, context):
        context.configuration.add(NtpServer(address="10.0.0.1", prefer=True))
        context.configuration.add(NtpServer(address="10.0.0.2"))
```

## Variable parameters

Parameters derived from the logical node's own attributes:

```python
class LoopbackIf(ConfigMap):
    def compile(self, context):
        lo0 = Loopback(
            index=0,
            name="Lo0",
            ipv4=f"192.0.2.{context.logical_node.id}/32",
        )
        context.configuration.add(lo0)
```

## External datasources

Pull live data from an integration at compile time:

```python
class LoopbackIf(ConfigMap):
    def compile(self, context):
        ip = context.integrations.ipam.data.ip_addresses(
            {"device": context.logical_node.hostname}
        )
        lo0 = Loopback(index=0, name="Lo0", ipv4=ip)
        context.configuration.add(lo0)
```

External values are resolved live on the first compile and cached in the database for subsequent compiles (stateful caching). To force a live refresh, use `resolve=True`.

## Available components

| Category | Components |
|----------|------------|
| System | `HostName`, `Contact`, `Location`, `DomainName`, `LoginBanner`, `MotdBanner` |
| SSH | `SshServer`, `AuthorizedKey` |
| Logging | `LoggingConfig`, `Console`, `VtyLine`, `RemoteServer`, `FileLogging` |
| NTP | `NtpServer` |
| SNMP | `SnmpGlobal`, `SnmpUser`, `SnmpServer`, `SnmpTrap`, `SnmpCommunity` |
| AAA | `aaaGlobal`, `aaaServerGroup`, `aaaTacacs`, `aaaRadius`, authentication/authorization/accounting methods |
| DHCP | `DHCPSnooping`, `DhcpRelayServer` |
| Interfaces | `FrontpanelPort`, `ManagementPort`, `LagInterface`, `Loopback`, `Subinterface`, `Svi` |
| Network Instances | `NetworkInstance`, `L3Vrf` |
| VLAN | `Vlan` |
| Routing | `StaticRoute`, `StaticRouteNextHop` |
| STP | `SpanningTreeGlobal`, `SpanningTreeRSTP`, `SpanningTreeMSTP`, `SpanningTreeMstpInstance`, `SpanningTreeRapidPVST` |
| ACL | `Ipv4Acl`, `Ipv6Acl`, `Ipv4AclEntry`, `Ipv6AclEntry` |
| LACP | `LacpConfig` |
| LLDP | `LldpConfig` |
| CDP | `CdpConfig` |
| VTP | `Vtp` |

## Registering ConfigMaps

ACE-X discovers ConfigMap instances by scanning Python files:

```python
ae = AutomationEngine()
ae.add_configmap_dir("./config_maps")   # scan all .py files in directory
```

Any module-level `ConfigMap` instance found in the scanned files is registered automatically.
