# Agents

ACE-X uses three long-running agents to bridge the backend to the outside world. Each agent polls the backend on a configurable interval, compares desired state to actual state, and reconciles.

## Collection Agent

**Purpose:** Pull running configs from network devices and upload them to ACE-X.

```mermaid
sequenceDiagram
    autonumber
    participant CA as Collection Agent
    participant BE as Backend API
    participant DEV as Network Device

    loop Every 60 seconds or when the manifest revision changes
        CA->>BE: Request manifest
        activate BE
        BE-->>CA: Return targets, credential IDs, and revision
        deactivate BE

        Note over CA,BE: Collect the configuration for each assigned target
        CA->>BE: Request decrypted credentials
        activate BE
        BE-->>CA: Return credentials
        deactivate BE

        CA->>DEV: Connect via SSH and request running configuration
        activate DEV
        DEV-->>CA: Return raw configuration
        deactivate DEV

        CA->>BE: Submit parsed observed configuration
        activate BE
        BE-->>CA: Confirm configuration received
        deactivate BE

        Note over CA,DEV: Discover the device's direct neighbors
        CA->>DEV: Request LLDP/CDP neighbor data
        activate DEV
        DEV-->>CA: Return neighbor data
        deactivate DEV

        CA->>BE: Submit discovered topology neighbors
        activate BE
        BE-->>CA: Confirm topology received
        deactivate BE

        CA->>BE: Acknowledge manifest revision
    end
```

The collection agent:

- Fetches a manifest from the backend listing which nodes to collect
- Re-triggers a collection cycle when `config_revision` changes (new nodes added, parameters changed)
- Uses up to 20 concurrent SSH connections
- Downloads and installs missing NED drivers from the backend via pip before every collection
  cycle — no driver is baked into the agent image, so a NED added or upgraded on the backend is
  picked up without rebuilding or restarting the agent (an upgrade of a driver the process has
  already imported is the exception and is logged as needing a restart)
- Parses the raw config through the NED driver's parser before uploading — the backend stores the structured `ComposedConfiguration`, not raw text

### Configuration

```bash
ACEX_API_URL=http://backend:8080
ACEX_AGENT_ID=<collection-agent-uuid>
ACEX_CLIENT_ID=collection-agent
ACEX_CLIENT_SECRET=...
ACEX_ISSUER_URL=http://keycloak:8180/realms/acex
```

## Telemetry Agent

**Purpose:** Keep a Telegraf configuration file in sync with ACE-X's desired observability state.

```mermaid
flowchart LR
    BE["Backend API"] -->|"renders config"| TA["Telemetry Agent"]
    TA -->|"writes telegraf.conf"| TG["Telegraf"]
    TG -->|"polls via SNMP"| DEV["Network Devices"]
    DEV -->|"returns metrics"| TG
    TG -->|"stores metrics"| IDB[("InfluxDB")]

    classDef service fill:#eef2ff,stroke:#818cf8,color:#1e1b4b
    classDef agent fill:#f0fdfa,stroke:#2dd4bf,color:#134e4a
    classDef device fill:#fff7ed,stroke:#fb923c,color:#7c2d12
    classDef database fill:#f5f3ff,stroke:#a78bfa,color:#4c1d95

    class BE service
    class TA,TG agent
    class DEV device
    class IDB database
```

The telemetry agent:

- Polls the backend every 60 seconds for its agent object
- Re-writes `telegraf.conf` when `config_revision` changes
- Does not run Telegraf itself — Telegraf is a co-located binary that reads the config file independently
- ACE-X generates the full Telegraf config from: SNMP input blocks (one per monitored node), ICMP inputs, syslog/trap inputs, and InfluxDB output blocks

### Configuration

```bash
ACEX_API_URL=http://backend:8080
ACEX_AGENT_ID=<telemetry-agent-uuid>
ACEX_CLIENT_ID=telemetry-agent
ACEX_CLIENT_SECRET=...
ACEX_ISSUER_URL=http://keycloak:8180/realms/acex
TELEGRAF_CONFIG_PATH=/etc/telegraf/telegraf.conf
```

## Grafana Sync

**Purpose:** Keep a Grafana instance in sync with ACE-X-generated dashboards and datasources.

```mermaid
sequenceDiagram
    participant GS as Grafana Sync
    participant BE as Backend API
    participant GF as Grafana

    loop Every 60 s
        GS->>BE: GET /observability/grafana/datasources
        GS->>BE: GET /observability/grafana/dashboards
        Note over GS: Compute SHA-256 of desired state
        alt Desired state changed or last apply failed
            GS->>GF: Ensure managed folder exists
            GS->>GF: Create/update datasources
            GS->>GF: Upsert dashboards
            GS->>GF: Delete orphaned dashboards (if prune=true)
        end
    end
```

The grafana-sync agent:

- Detects changes via a SHA-256 digest of the full desired state — avoids unnecessary API calls
- Only manages dashboards in its own folder — never touches user-created dashboards in other folders
- Retries on the next cycle if an apply fails

### Configuration

```bash
ACEX_API_URL=http://backend:8080
ACEX_CLIENT_ID=grafana-sync
ACEX_CLIENT_SECRET=...
ACEX_ISSUER_URL=http://keycloak:8180/realms/acex
GRAFANA_URL=http://grafana:3000
GRAFANA_TOKEN=...
```
