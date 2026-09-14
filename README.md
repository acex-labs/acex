# ACE-X

**An implementation of the ACE architecture — Automation & Control Ecosystem.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

ACE-X manages networks by keeping **what the network should be** strictly apart from **the hardware that happens to run it** and from **what the devices actually report back**. Configuration is written as code against logical nodes, rendered to real hardware through drivers, read back through the same drivers, and continuously compared.

The result is a system where infrastructure changes go through review and land in a maintenance window, while services are delivered on demand — without the two blocking each other.

---

## The ACE architecture

ACE is an architecture for administering and automating networks. It describes how to organise the problem — not how to write the code. ACE-X is one implementation of it; the sections after this one describe how ACE-X in particular does the job.

The architecture rests on seven ideas.

### 1. The logical network is separate from the hardware that runs it

Networks are traditionally administered as a set of devices. ACE separates them into two independent things.

A **logical node** is a participant in the network: its identity, its role, its place, and all of its configuration. It is what the network design is expressed in.

An **asset** is a piece of hardware: a make, a model, a serial number, a software version. Nothing more. It holds no configuration and has no identity in the network.

A **node** is a binding between the two, and it has a lifecycle of its own — planned, installed, active, retired.

```
logical node          asset
 identity              make / model
 role                  serial
 place        ──┬──    software version
 configuration  │
                │
              node
      binding + lifecycle
```

The separation is not bookkeeping. It changes what is possible:

- Design and configuration exist before any hardware does. A site can be fully specified and its configuration generated while the equipment is still on order.
- Replacing failed hardware rebinds an asset. The network design is untouched, because the design never referred to that serial number.
- Several pieces of hardware can present as one logical participant — a stack, a chassis pair, a redundant pair — without the design knowing or caring.

### 2. One neutral model in the middle, and symmetric translation

ACE defines a **vendor-neutral model** of what a network node is configured to do. It is the only representation the architecture works in.

Translation to and from any particular platform happens in one place, a **driver**, and it works in both directions:

- **outward** — the neutral model becomes configuration for a specific platform
- **inward** — a specific platform's configuration becomes the neutral model

One driver, both directions. Because the same driver owns both translations, the two cannot disagree about what a given construct means. And because everything above the driver speaks only the neutral model, no part of the system other than a driver knows which vendors exist.

This is what makes the rest of the architecture possible: intent and reality end up expressed in the same terms, so they can be compared.

```mermaid
flowchart LR
    INT["Declared intent"] --> DES["Desired state"]
    DES --> DIFF{{"Compare"}}
    OBS["Observed state"] --> DIFF
    DIFF --> COMP["Compliance"]
    DIFF --> CHG["Proposed change"]
    CHG -->|"decision"| DRV
    DRV["Driver<br/>translates both ways"] --> DEV(["Network element"])
    DEV --> DRV
    DRV --> OBS
```

### 3. State is declared and derived, never stored

Desired state is not a document that is edited and saved. It is **derived on demand** from declared intent, every time it is asked for.

The consequence is that desired state cannot go stale and cannot drift from the declaration that produced it. There is no saved artefact to forget to regenerate, and no second copy to reconcile.

The same rule applies to measurement. **What to measure is also declared state**, derived from the network's inventory and its configuration rather than configured per device. If a node exists and its configuration says it does something worth watching, the measurement for it follows — and stops following when it does not. Monitoring cannot fall behind the network, because it is not maintained separately from it.

### 4. Configuration has two planes, with independent lifecycles

This is the idea ACE exists for.

Configuration on a network element arrives from two fundamentally different directions, and they are almost always conflated:

**Infrastructure** — how the network is built. It changes slowly and deliberately. It should be written down, reviewed by a second pair of eyes, versioned, and applied when the organisation has agreed it is safe to apply.

**Services** — what the network delivers. It changes constantly and on demand, driven by orders and events. Its value is largely in how fast it can be fulfilled.

Treating these as one thing forces a choice, and both answers are bad. Automate everything, and an infrastructure change reaches production the moment someone merges it. Gate everything, and every service delivery waits for a change window.

|  | **Infrastructure** | **Services** |
|---|---|---|
| Changes | Slowly, deliberately | Continuously, on demand |
| Authority | Review and agreement | An order or an event |
| Delivery | Deferred — produces a proposed change | Direct — closed loop |
| Applied | When the organisation decides | On fulfilment |
| Optimised for | Control and auditability | Lead time |

ACE keeps them as **separate planes over a shared model**. Both contribute to the same node's configuration, but each keeps its own lifecycle. An infrastructure change becomes a proposal that waits for a decision. A service is fulfilled when it is ordered — and fulfilling it must not drag a pending infrastructure change onto the element along with it.

**Control over infrastructure, without putting services in a queue behind it.**

### 5. Difference is the measurement; applying it is a decision

Because intent and reality are expressed in the same model, the distance between them can be computed continuously and reported as **compliance** — per element, per site, across the estate.

A difference is not a fault. Between change windows, a network that differs from its declared intent is behaving exactly as expected. Measuring that distance is a permanent, passive activity; closing it is a separate, deliberate act.

When the decision is made, the difference is expressed as the **smallest change that closes it** — not a wholesale replacement of the element's configuration. A change is reviewable before it is made, and narrow enough to reason about.

Change in the other direction — reality diverging because someone altered an element directly — is handled by turning reality back into declared intent, so unmanaged change re-enters the system through review rather than being silently overwritten. The same path lets an existing, unmanaged network be adopted rather than rebuilt.

### 6. Observation is distributed, pulled, and granted

The core of an ACE system holds declared state. It does not reach out to network elements itself.

Observation is performed by **collectors** placed where they can see what they need to see. A collector asks the core what it should be doing, does it, and reports what it reached. Nothing is pushed to a collector, so collectors work across firewalls, management networks and isolated segments without the core needing a path into any of them — and more of them can be added without the core changing.

What a collector may do is **granted**, not configured. Each is given a set of capabilities and a scope of the network, and receives only the work that falls inside both. Where observation happens, and by what means, is a matter of policy rather than of per-device setup.

### 7. Three kinds of data, kept distinct

ACE distinguishes three classes of data and does not let them borrow each other's shape:

| | What it is |
|---|---|
| **Desired configuration** | What an element should be configured to do |
| **Observed configuration** | What it is actually configured to do |
| **Operational data** | What it reports about its running state |

The first two share one model deliberately — that is precisely what makes them comparable, and it is the basis of compliance.

Operational data deliberately does not. Neighbour relationships, routing state, protocol adjacencies, counters — these are not configuration and never were. Forcing them into a configuration model would only make them diffable against something they are not. So operational data is modelled on its own terms, per kind of data, carrying the time it was observed, and correlated back to the network inventory — which also means it can reveal what is attached to the network that was never declared to be there.

Physical reality is expected to become **declared** in time, as designed cabling and connectivity. When it does, the desired-versus-observed comparison extends down into the physical layer as well: wired as designed, or wired as someone on site decided that morning.

---

## How ACE-X implements it

The rest of this document is ACE-X specifically: intent declared as Python, a concrete neutral model, drivers for real platforms, and the interfaces around them.

## Configuration as code

A config map is a Python class with a `compile()` method and a filter that decides which logical nodes it applies to.

```python
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Loopback


class MplsLoopback(ConfigMap):
    def compile(self, context):
        context.configuration.add(
            Loopback(
                index=0,
                name="Lo0",
                description="MPLS Loopback",
                ipv4=f"192.0.2.{context.logical_node.sequence}/32",
            )
        )


mpls_loopback = MplsLoopback()
mpls_loopback.filters = FilterAttribute("role").eq("core")
```

Filters compose, so placement stays declarative:

```python
cm.filters = FilterAttribute("site").eq("hq")
cm.filters = FilterAttribute("site").eq("hq") & FilterAttribute("role").eq("core")
cm.filters = FilterAttribute("role").eq("core") | FilterAttribute("role").eq("edge")
```

### Values from an external source of truth

Intent can reference a query against an integration rather than a literal:

```python
Loopback(
    index=0,
    name="Lo0",
    ipv4=context.integrations.ipam.data.ip_addresses({"role": "loopback"}),
)
```

Resolution is an **explicit operation**, not a side effect of compiling. Resolved values are persisted with their pointer, query, kind and `resolved_at` timestamp — so a compile is reproducible without reaching out to external systems, and every externally sourced value can be traced to when it was last confirmed.

### The configuration model

One vendor-neutral tree, `ComposedConfiguration`, is the pivot for everything:

| Area | Components |
|---|---|
| System | HostName, Contact, Location, DomainName, DnsServer, Clock, LoginBanner, MotdBanner |
| Access | SshServer, AuthorizedKey, VtyLine |
| AAA | aaaGlobal, aaaServerGroup, aaaTacacs, aaaRadius, authentication / authorization / accounting methods and events |
| Logging | LoggingConfig, Console, RemoteServer, FileLogging, LoggingEvent |
| SNMP | SnmpGlobal, SnmpUser, SnmpGroup, SnmpView, SnmpServer, SnmpTrap, SnmpCommunity |
| Interfaces | FrontpanelPort, ManagementPort, LagInterface, Loopback, Subinterface, Svi, InterfaceTemplate |
| L2 / L3 | Vlan, L2Domain, L3Vrf, StaticRoute, StaticRouteNextHop, Routing |
| Control protocols | SpanningTree (Global / RSTP / MSTP / RapidPVST), LacpConfig, LldpConfig, CdpConfig, Vtp |
| Security | Ipv4Acl, Ipv6Acl, Ipv4AclEntry, Ipv6AclEntry, DHCPSnooping, DhcpRelayServer |
| Flow export | NetflowGlobalConfig, NetflowExporter, NetflowCollector, NetflowRecord, SflowCollector, SfloGlobalConfig |
| Services | NtpServer, Services |

**69 component types** in total, with vendor-specific `Augment` components for the cases a neutral model should not pretend to cover.

---

## Observability and collection

ACE-X implements declared measurement as **telemetry components**. Each one binds together, in a single object, the four views of one metric that normally drift apart in separate systems:

- what a collector must do to obtain it
- the measurement name and tag schema it produces
- the identity used to query it from a dashboard
- the capability that gates its collection, and the node it belongs to

Telemetry components are produced by **providers** — functions that inspect inventory and configuration and yield the components implied by what they find. The resulting registry is deliberately **not persisted**: it is rebuilt on every request, then rendered into Telegraf collector configuration and into Grafana dashboards and datasources. There is no stored copy to fall out of step with the network.

Collection runs as **agents**, each of which polls a manifest, applies it, and acknowledges the revision it reached:

| Agent | Does |
|---|---|
| **collection-agent** | Fetches running configurations and LLDP neighbours through NEDs, uploads them as observed state |
| **telemetry-agent** | Keeps a local `telegraf.conf` in sync with the rendered central configuration |
| **grafana-sync** | Reconciles a Grafana instance against generated dashboards and datasources, hashing desired state to no-op when nothing changed |

Agents are granted capabilities from a fixed vocabulary — `icmp`, `snmp`, `snmp_trap`, `mdt`, `syslog_rfc5424` — plus an explicit set of nodes or a match rule. An agent receives only the work covered by both, so a collector in a segmented site never learns about the rest of the estate.

Secrets are never part of a manifest. A manifest carries credential **references** per target — a login, a privilege-escalation credential — and the agent redeems each reference against the credential API only when it is about to connect. The store behind it is backed by Fernet encryption or HashiCorp Vault, with credentials assigned per node or per site.

---

## Interfaces

Everything talks to the same REST API. The web UI, the CLI and the AI tooling are peers, not layers.

**REST API** — OpenAPI at `/api/v1/docs`, OIDC-protected.

```
/api/v1/inventory/{nodes,logical_nodes,assets,sites,regions,contacts,...}
/api/v1/inventory/node_instances/{id}/configuration/desired      # rendered via NED
/api/v1/inventory/node_instances/{id}/configuration/observed     # snapshot history
/api/v1/inventory/node_instances/{id}/configuration/intent_diff  # desired vs observed
/api/v1/operations/compliance/{node_instance_id}
/api/v1/operations/compliance/site/{site_name}
/api/v1/config_components/{generate,reconcile,translate}
/api/v1/observability/agents                                     # manifest, config, ack
/api/v1/observability/grafana/{dashboards,datasources}           # generated definitions
/api/v1/health
```

**CLI** — `pip install acex-cli`

```bash
acex node list --site hq --role core
acex node config show desired r1 --path system.ntp     # compiled intent
acex node config show observed r1                      # what the device reports
acex node config show local r1 --dir ./config_maps     # compile locally, no backend
acex node config diff plan r1                          # desired vs observed, as a tree
acex node config diff plan r1 --format commands         # as the patch that would be sent
acex node config diff apply r1                         # review, confirm, send
acex node connect r1
```

**MCP server** — `pip install acex-mcp`

A curated, read-only tool surface over inventory, configuration and topology, with token pass-through auth. Point Claude Code, Claude Desktop or any MCP client at it and ask about the network in plain language.

**AI Ops** — Built into the backend. Named providers with ordered failover chains, configurable in `app.py` or entirely through `ACEX_AI_*` environment variables. The assistant can *suggest* opening a page in the UI; the user always clicks. It never navigates on its own.

---

## Web UI

The frontend lives in its own repository: **[acex-labs/acex-frontend](https://github.com/acex-labs/acex-frontend)**

React 19 + Vite + Tailwind, OIDC via `oidc-client-ts`, TanStack Query against the ACE-X API. Topology is rendered with React Flow, geography with Leaflet.

It is organised as **modules** — self-contained verticals that register their own navigation and code-split routes. Adding one is a single file plus one line in the registry.

| Module | Contains |
|---|---|
| **Network** | Nodes, Sites, Regions, Logical Nodes, Assets, Contacts, Import |
| **Configs** | Config Maps, Builder, Reconcile, Translator, NEDs |
| **Observe** | Dashboards, Config History, ICMP, Telemetry |
| **Operations** | Workflows, Bulk Actions, Triggers, Scheduled |
| **Autopilot** | AI Ops, Agents |
| **Settings** | Credentials, Telemetry Agents, Collection Agents |
| **Platform** | Admin (only visible in admin mode) |

Node and site detail pages carry tabs for configuration, hardware, LLDP neighbours, snapshot history and site topology.

---

## Extending ACE-X

Every extension point is a separately installable, independently versioned package. The core is never modified.

**NEDs (Network Element Drivers)** — a renderer, a parser and a transport. Chosen per asset via `ned_id`, so one installation drives mixed-vendor estates.

```python
from acex_devkit.drivers import NetworkElementDriver

class MyDriver(NetworkElementDriver):
    renderer_class = MyRenderer   # ComposedConfiguration + Asset → device config
    parser_class   = MyParser     # device config → ComposedConfiguration
    transport_class = MyTransport # get_config / send_config / execute
```

Shipped: `acex-driver-cisco-ioscli`, `acex-driver-juniper-junoscli` — with **121 hardware model definitions** describing real port layouts.

**Config normalizers** — declarative rules that strip non-intent lines (counters, timestamps) and redact secrets from collected configurations, in two isolated passes, so diffs mean something and secrets are never stored.

**Integration plugins** — adapters that back inventory objects with an external source of truth (NetBox is included) or expose queryable data to config maps.

**Telemetry providers** — functions that inspect ACE-X state and yield telemetry components, registered with `register_provider`.

**Agents** — anything that polls a manifest, applies it and acknowledges a revision.

---

## Repository layout

```
backend/    acex           — automation engine, API, config compiler, observability
devkit/     acex-devkit    — ComposedConfiguration, differ, NED base classes, normalizer
client/     acex-client    — typed REST client
cli/        acex-cli       — command line interface
mcp/        acex-mcp       — MCP server
worker/     acex-worker    — distributed task execution (scaffold)
drivers/    NEDs           — cisco_ios_cli, juniper_junos_cli
agents/     collection-agent, telemetry-agent, grafana-sync
mock-device/               — SSH + SNMP device simulator for development
docs/                      — integration examples
```

| Package | Install |
|---|---|
| **acex** | `pip install acex` |
| **acex-cli** | `pip install acex-cli` |
| **acex-devkit** | `pip install acex-devkit` |
| **acex-client** | `pip install acex-client` |
| **acex-mcp** | `pip install acex-mcp` |

---

## Quick start

The full stack — backend, frontend, Postgres, InfluxDB, Grafana, Keycloak, Vault, three agents and six simulated devices — comes up with one command.

```bash
git clone https://github.com/acex-labs/acex.git
cd acex
./setup.sh          # or: task setup
```

`setup.sh` adds a hosts entry for Keycloak, creates `.env`, clones the frontend next to this repo, builds and starts everything.

```
Frontend   http://localhost:3000     admin / admin
Backend    http://localhost:8080     /api/v1/docs
Grafana    http://localhost:3001     admin / admin
Keycloak   http://keycloak:8180      admin / admin
```

Then seed simulated devices and agents:

```bash
task seed
```

Common tasks: `task up`, `task down`, `task logs -- backend`, `task ps`, `task reset`.

### Running the engine yourself

```python
from acex import AutomationEngine
from acex.database import Connection
from acex.plugins.integrations.netbox import Netbox

db = Connection(dbname="acex", user="postgres", host="localhost", backend="postgresql")

ae = AutomationEngine(db_connection=db)
ae.add_integration("ipam", Netbox(url="https://netbox.example.net/", token=NETBOX_TOKEN))
ae.add_configmap_dir("config_maps")
ae.add_cors_allowed_origin("https://acex.example.net")

app = ae.create_app()
```

```bash
python -m acex
```

Migrations run on startup. See [`docs/examples/example1/`](docs/examples/example1/) for a complete application, and [`DEVELOPMENT.md`](DEVELOPMENT.md) for working on the packages themselves.

---

## Project status

ACE-X is under active development and pre-1.0 as a whole, though individual packages are further along than others.

**Working today**

- Inventory: assets, asset clusters, logical nodes, nodes, sites, regions, contacts, credentials, management connections
- Configuration as code: config maps, filters, 69 component types, external value resolution with provenance
- Vendor-neutral model with rendering and parsing through NEDs (Cisco IOS, Juniper Junos)
- Observed configuration collection, snapshot history, normalization and secret masking
- Structural desired-vs-observed diff, compliance per node and per site
- Patch rendering and operator-confirmed apply through the CLI (`config diff plan` / `apply`)
- Reconcile and translate — drift and brownfield configs back into config map source
- Declarative observability: telemetry components, capability-gated agents, generated collector configs, generated Grafana dashboards and datasources
- Operational data as its own class: LLDP collection, neighbour-to-inventory correlation, per-site topology graph
- REST API with OIDC, typed client, CLI, MCP server, AI Ops with provider failover
- Web UI: Network, Configs and Settings modules

**On the roadmap**

- **The service plane.** Closed-loop service delivery — the second half of section 3 — is designed but not yet built. Today all configuration enters through the IaC plane.
- **Maintenance windows and change approval.** Applying a patch works, but the window itself is not yet a modelled object: no scheduling, no approval record, no audit trail of who applied which patch when.
- **Operations module** — workflows, bulk actions, triggers and scheduling are scaffolded in the UI, not implemented.
- **Declared physical topology.** Planned cabling as intent, so observed LLDP can be diffed against how the network was designed to be wired.
- **More operational data types** — routing state and others, each with its own model rather than bent into the configuration tree.
- Streaming telemetry (MDT) and syslog ingestion beyond the declared capability vocabulary.
- The worker package is a scaffold; distributed task execution is not implemented.

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md), and [DEVELOPMENT.md](DEVELOPMENT.md) for environment setup, branch naming and the pre-commit hooks.

Branches follow `<prefix>/<description>` with Conventional Commits prefixes — `feat/add-ntp-support`, `fix/static-route-nil-check`.

## License

**GNU Affero General Public License v3.0** — see [LICENSE](LICENSE).

- ✅ Free to use for any purpose
- ✅ Full source available, modify freely
- ⚠️ If you modify ACE-X and run it as a network service, you must share your modifications
- ⚠️ Derivative works must also be AGPL-licensed

The AGPL keeps improvements flowing back to everyone who relies on ACE-X, including when it is run as a service.

**Commercial licences** are available for organisations that need to use ACE-X without AGPL obligations — contact **license@acex.dev**.

## Sponsors

### Essity — main sponsor

**[Essity](https://www.essity.com)** is ACE-X's main sponsor and has backed the project since its early days.

Early sponsorship is rare, and Essity's came while ACE-X was still finding its shape as a product. It gave the work room to move faster and a real network environment to be tested against. That is a contribution worth naming, and we are grateful for it.

### Sponsoring ACE-X

If your organisation depends on ACE-X, or wants to shape where it goes next, sponsorship directly funds development, drivers for additional vendors, and documentation. Get in touch at **license@acex.dev**.

## Adopters

**[Acebit](https://www.acebit.se)** has used ACE-X in customer projects since early on. Running the framework against real networks, on real deadlines, is what turned it from a design into something that holds up in production.

## Authors

ACE-X was conceived and originated by **Johan Lahti** — the idea, the architecture and the product are his from the outset. The original codebase was written on his own time and contributed to the project under the AGPL.

**Johan Lahti** &lt;johan.lahti@acebit.se&gt; — creator and maintainer
**Jani Naamanka** &lt;jani@naacon.se&gt; — co-author
**Isak Ljunggren** &lt;isak.ljunggren@acebit.se&gt; — co-author

## Links

- Backend and packages — https://github.com/acex-labs/acex
- Web UI — https://github.com/acex-labs/acex-frontend
- Issues — https://github.com/acex-labs/acex/issues
