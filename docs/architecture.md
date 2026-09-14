# Architecture

## System overview

ACE-X is structured as a backend API surrounded by lightweight agents that bridge it to the outside world — network devices, observability tools, and AI assistants.

```mermaid
graph TB
    subgraph Integrations
        NB[NetBox / IPAM]
        VLT[Vault]
    end

    subgraph Core
        BE[Backend API<br/>FastAPI]
        DB[(PostgreSQL)]
        KC[Keycloak<br/>OIDC]
    end

    subgraph Agents
        CA[Collection Agent]
        TA[Telemetry Agent]
        GS[Grafana Sync]
    end

    subgraph Observability
        TG[Telegraf]
        IDB[(InfluxDB)]
        GF[Grafana]
    end

    subgraph Devices
        D1[Router / Switch]
        D2[Router / Switch]
    end

    CLI[acex-cli] -->|REST| BE
    MCP[MCP Server] -->|REST| BE
    BE <-->|read inventory| NB
    BE -->|read secrets| VLT
    BE <-->|validate JWT| KC
    BE --- DB

    CA -->|fetch manifest| BE
    CA -->|upload observed config| BE
    CA <-->|SSH show run| D1
    CA <-->|SSH show run| D2

    TA -->|fetch Telegraf config| BE
    TA -->|write telegraf.conf| TG
    TG -->|metrics| IDB

    GS -->|fetch dashboards & datasources| BE
    GS <-->|upsert dashboards| GF
    GF -->|query| IDB
```

## Data model

Three core entities connect physical hardware to vendor-agnostic configuration:

| Entity | What it is |
|--------|------------|
| **Asset** | A physical device (serial number, hardware model, NED driver assignment) |
| **Logical Node** | A configuration template — compiled ConfigMaps produce a `ComposedConfiguration` for this node |
| **Node Instance** | A deployed node: one Asset bound to one Logical Node, with a management IP and SSH credentials |

## Config compilation flow

From a Python ConfigMap to CLI commands on a device:

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant BE as Backend API
    participant DB as PostgreSQL
    participant NB as NetBox / IPAM
    participant DRV as NED Driver
    participant DEV as Network Device

    Dev->>BE: Register ConfigMaps (add_configmap_dir)
    Dev->>BE: Trigger compile (POST /compile)
    BE->>NB: Resolve ExternalValues (live data lookup)
    NB-->>BE: IP addresses, device data
    BE->>DB: Store ComposedConfiguration
    DB-->>BE: ok

    Dev->>BE: GET desired config (--render)
    BE->>DRV: render(ComposedConfiguration, asset)
    DRV-->>BE: Vendor CLI string

    Dev->>BE: config diff plan
    BE->>DB: fetch observed config
    DB-->>BE: last collected running config
    BE->>DRV: render_patch(diff)
    DRV-->>BE: Patch commands
    BE-->>Dev: Show diff + commands

    Dev->>BE: config diff apply (confirm)
    BE->>DRV: transport.send_config(commands)
    DRV->>DEV: SSH — send patch commands
    DEV-->>DRV: ok
```

## Observability flow

How device metrics get from a router to a Grafana dashboard:

```mermaid
flowchart LR
    BE[Backend API] -->|render Telegraf config| TA[Telemetry Agent]
    TA -->|write telegraf.conf| TG[Telegraf]
    TG -->|SNMP poll| DEV[Network Device]
    DEV -->|SNMP response| TG
    TG -->|write metrics| IDB[(InfluxDB)]
    BE -->|generate dashboards + datasources| GS[Grafana Sync]
    GS -->|upsert| GF[Grafana]
    GF -->|Flux/InfluxQL query| IDB
```

## Collection agent flow

How observed configs are kept up to date:

```mermaid
sequenceDiagram
    participant CA as Collection Agent
    participant BE as Backend API
    participant DRV as NED Driver
    participant DEV as Network Device

    loop Every 60 seconds
        CA->>BE: GET manifest (node list + config_revision)
        BE-->>CA: Targets + credential IDs
        CA->>BE: GET decrypted credentials
        BE-->>CA: SSH credentials (from Vault or DB)
        CA->>DEV: SSH — show running-config
        DEV-->>CA: Raw config text
        CA->>DRV: parser.parse(raw)
        DRV-->>CA: ComposedConfiguration
        CA->>BE: POST observed config
        CA->>DEV: SSH — show lldp neighbors
        DEV-->>CA: Neighbor data
        CA->>BE: POST topology neighbors
        CA->>BE: ACK manifest revision
    end
```

## NED driver architecture

Drivers (NEDs) are Python packages loaded as setuptools entry points. Each driver implements four roles:

```mermaid
graph LR
    CC[ComposedConfiguration] --> R[Renderer<br/>render]
    R --> CLI[Vendor CLI config]

    DIFF[Diff] --> RP[Renderer<br/>render_patch]
    RP --> PATCH[Patch commands]

    DEV[Network Device] --> T[Transport<br/>get_config]
    T --> RAW[Raw show run]
    RAW --> P[Parser<br/>parse]
    P --> CC2[ComposedConfiguration]

    CMD[Patch commands] --> T2[Transport<br/>send_config]
    T2 --> DEV
```

## GitHub → GitLab build trigger

On every push to `main` and on release events, a GitHub Actions workflow triggers a downstream GitLab pipeline via the GitLab pipeline trigger API. This is a one-way call — GitHub fires the trigger, GitLab builds independently.

```mermaid
sequenceDiagram
    participant GH as GitHub Actions
    participant GL as GitLab CI

    GH->>GL: POST /trigger/pipeline<br/>(token + BUILD_TARGET=acex)
    GL-->>GH: 201 Created
    Note over GL: GitLab builds downstream NaaS artifact
```
