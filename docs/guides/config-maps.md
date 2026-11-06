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

## Syncing ConfigMaps from git

ConfigMaps can also be read from a git repository, so the backend needs nothing mounted. Add the
repository under **Settings > Git Repositories** in the web interface, or through the API as below; the backend checks it out, loads the ConfigMaps in it the same way as
from a directory, and loads them again when the branch moves.

1. Create a personal access token on the git host with read access to the repository, and store it as a
   `token` credential:

    ```bash
    curl -X POST $ACEX/api/v1/inventory/credentials \
      -d '{"name": "config-maps-pat", "credential_type": "token", "fields": {"token": "<PAT>"}}'
    ```

2. Add the repository, naming the credential's id:

    ```bash
    curl -X POST $ACEX/api/v1/git_repositories -d '{
      "name": "network-config",
      "url": "https://github.com/example/network-config.git",
      "branch": "main",
      "path": "config_maps",
      "auth_method": "https_token",
      "credential_id": 12
    }'
    ```

    The answer says which commit was loaded (`commit`), which ConfigMaps it holds (`config_maps`) and,
    if it failed, why (`last_error`).

| Field | Meaning |
|---|---|
| `url` | The HTTPS clone URL. Credentials in the URL are refused. |
| `branch` | The branch to follow. Default `main`. |
| `path` | The directory in the repository that holds the ConfigMaps. Empty for its root. |
| `auth_method` | `https_token`: a personal access token from a `token` credential. `https_anonymous`: a public repository. |
| `credential_id` | The credential holding the token. A Vault-backed credential works too. |
| `username` | Sent with the token. Most hosts accept any; Bitbucket wants the account's username. |
| `ca_certificate` | PEM certificates to trust for the host, for one whose certificate an internal CA signed. Include intermediates the host doesn't send. Left out, the system's trusted CAs are used. |
| `enabled` | A disabled repository is not synced and its ConfigMaps are not used. |

### When ConfigMaps are loaded again

Every API process checks each repository when it starts and then every 30 minutes. A check asks the host
for the branch's latest commit (`git ls-remote`); only when it has moved, or the repository's settings
changed, is the commit fetched and loaded. `POST /api/v1/git_repositories/{id}/sync` fetches and loads
the latest commit at once.

A commit is loaded only if every file in it imports. If one fails, the ConfigMaps already loaded stay in
use and `last_error` names the file, so a broken push never leaves devices compiled from part of the
ConfigMaps. The commit is not tried again until the branch moves or a sync is requested.

If the host can't be reached, the loaded ConfigMaps stay in use. A process that starts while the host is
unreachable loads the last checkout, if `ACEX_GIT_SYNC_CHECKOUT_DIR` points at a volume that kept it.

With several API processes, the one that answers a change loads it at once; the others pick it up at
their next check. `config_maps` in an answer is what the answering process has loaded.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `ACEX_GIT_SYNC_POLL_INTERVAL_SECONDS` | `1800` | How often each repository is checked. At least 60. |
| `ACEX_GIT_SYNC_CHECKOUT_DIR` | a directory under the system temp directory | Where repositories are checked out. |
| `ACEX_GIT_SYNC_TIMEOUT_SECONDS` | `120` | How long one git command may run. |

!!! warning
    A ConfigMap is Python code that the backend runs. Anyone who can change the repository, or point the
    backend at another one, can run code on the backend. Keep write access to the repository as tight as
    access to the backend itself.

A host signed by an internal CA fails with `SSL certificate problem: unable to get local issuer certificate`.
Give the repository the CA chain as `ca_certificate` (in the web interface: *Trust an internal CA…*), or
trust the CA for every repository by building it into the backend image's trust store or pointing
`GIT_SSL_CAINFO` at a bundle. Turning certificate checks off is not offered: the token would go to whoever
can intercept the connection.

The token never appears in a URL, in the checkout's `.git/config` or on a command line: git reads it from
the environment of the one command that needs it.
