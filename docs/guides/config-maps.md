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
| `site` | Set, the repository belongs to this site: its ConfigMaps apply to the logical nodes of that site only. Left out, they apply to any site their filters say. See below. |
| `webhook_credential_id` | A `token` credential whose token is the secret of the repository's webhook, so that a push syncs it at once. See below. Empty: no webhook. |
| `merge_request_credential_id` | A `token` credential that merge requests are sent with, so that a ConfigMap made in ACEX can be proposed to the repository. See below. Empty: none can be sent. GitLab only. |
| `enabled` | A disabled repository is not synced and its ConfigMaps are not used. |

### One repository for each site

Give a repository a `site` and the ConfigMaps in it can only ever apply to the logical nodes of that site. The
ConfigMaps' own filters still apply, on top of it: a ConfigMap with `FilterAttribute("role").eq("core")` in the
repository of site `got` applies to the core nodes of `got`, and to no core node of another site. A node with no
site is never reached by a repository that has one.

This is how several teams, or a customer's sites, each work from a repository of their own without being able to
change another site's devices. Add one repository for each site:

```bash
curl -X POST $ACEX/api/v1/git_repositories -d '{
  "name": "got-config", "url": "https://github.com/example/got-config.git",
  "auth_method": "https_token", "credential_id": 12, "site": "got"
}'
```

The site is the name the logical nodes carry (`site` in their filters), written the same way, and the match is exact.
A name that no node has is not an error: the repository then applies to nothing. Send `"site": null` to a repository
to take the limit away again. A repository without a `site` is not limited, so keep the repositories of the sites
you want to separate all set.

### Syncing at once with a webhook

A branch is checked every 30 minutes. A git host can tell ACEX when the branch has a new commit instead, and the repository is
then synced within seconds.

1. Make a `token` credential whose token is the secret of the webhook: a long random string that only the git host and ACEX
   know. It is not a token of the git host.
2. Give the repository the id of that credential, as `webhook_credential_id`, when you add it or in a `PATCH`. `null` removes the
   webhook.
3. In the git host, add a webhook that calls `https://<the API>/api/v1/git_repositories/<repository id>/webhook` for push events
   with that secret.

    - GitLab: **Settings > Webhooks**. Put the secret in **Secret token** and tick **Push events**, with the branch the repository
      follows. GitLab refuses an address on a private network unless an administrator allows it (**Admin > Settings > Network >
      Outbound requests**).
    - GitHub: **Settings > Webhooks**. Content type `application/json`, the secret in **Secret**, and **Just the push event**.

The call needs no login, only the secret: GitLab sends it as `X-Gitlab-Token` and GitHub signs the body with it
(`X-Hub-Signature-256`). The answers:

| Answer | Meaning |
|---|---|
| `202` | A push to the branch the repository follows. It is synced in the background. |
| `200` | Nothing to do: a ping, a push to another branch or a tag, a deleted branch, or another kind of event. |
| `401` | The secret does not match. |
| `404` | The repository does not exist, is disabled, or has no webhook (or its credential is gone). |

The API process that answers loads the new commit at once. With several API processes, the others pick it up at their next
check. Syncing is the same as `POST /api/v1/git_repositories/{id}/sync`, so a failed sync shows in `last_error` as usual.

### Sending a ConfigMap as a merge request

A ConfigMap made in ACEX, for example by the Config Translator, can be sent to a repository as a merge request instead of being
copied there by hand. ACEX commits the file to a new branch and opens a merge request into the branch the repository follows.
Nothing changes on that branch, or on any device, until someone merges it on the git host. GitLab only.

1. In GitLab, make a token that may write to the project through the API: a project access token with the role **Developer** and
   the scope **api**. The token the repository is read with is not enough: `read_repository` and `write_repository` are for git
   itself, not for the API.
2. Store it as a `token` credential and give the repository the id of that credential, as `merge_request_credential_id`, when
   you add it or in a `PATCH` (in the web interface: **Merge request token**). `null` takes it away again.
3. Keep the followed branch protected in GitLab, so that only people merge into it. ACEX never merges.

In the web interface, **Create merge request** is next to the code that the Config Translator, the Builder and Reconcile
generate: choose the repository, the folder and a file name. Through the API:

```bash
curl $ACEX/api/v1/git_repositories/3/tree
curl -X POST $ACEX/api/v1/git_repositories/3/merge_requests -d '{
  "path": "got/ntp.py",
  "content": "from acex.config_map import ConfigMap\n...",
  "title": "Add NTP for got",
  "description": "Translated from the core switch."
}'
```

`tree` lists the directories and files of the followed branch, as GitLab has them now. The answer to the second call has the
address of the merge request (`url`), its number and the new branch, named `acex/<file name>-<six characters>`.

- The file goes where `path` says, anywhere in the repository, and a directory that does not exist yet is made. ACEX reads
  ConfigMaps only under the repository's own `path`: a file outside that directory can be merged but is not used, unless
  another repository entry reads the directory it is in. With one repository entry for each site, the directory decides which
  site the ConfigMap reaches.
- The path names a `.py` file and the content is Python that parses. A path that already holds a file is refused unless
  `replace` is true; the merge request then changes that file.
- The merge request is opened by the token's own user (GitLab makes a bot user for a project access token) and its text names
  the ACEX user who sent it. The commit is written in that user's name when their login carries an email address.
- Every signed-in user of ACEX can send one, like the rest of the git repository API.
- The project is the path of the repository's `url` on its host. A GitLab served under a sub-path of its host is not supported.
- The token is sent to the host in the repository's `url` and to no other. Whoever can change a repository can change that
  address, so keep that as tight as access to the token itself.
- A host signed by an internal CA is trusted through the repository's `ca_certificate`, as for syncing. These calls check a
  certificate more strictly than git does (by RFC 5280, for example an authority key identifier), so a certificate that git
  accepts can be refused here; the answer says what is missing.

| Answer | Meaning |
|---|---|
| `201` | The merge request is open. |
| `409` | The repository has no merge request token (or its credential is gone), or the path already holds a file and `replace` is not set. |
| `422` | The path is not a `.py` file inside the repository, the title is empty, or the content is not Python. |
| `502` | GitLab refused or could not be reached. `detail` says what it answered: a wrong or expired token, a token without the scope or the role, a project or a branch it does not have. |

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
