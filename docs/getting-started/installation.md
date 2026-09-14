# Installation

## Requirements

- Python 3.13+
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker + Docker Compose v2 (for the full local stack)
- [`task`](https://taskfile.dev/#/installation) (optional but recommended)

## Full local stack (recommended)

The fastest way to run a complete ACE-X environment — backend, frontend, agents, mock devices, Grafana, Keycloak, InfluxDB — is with Docker Compose.

```bash
git clone git@github.com:acex-labs/acex.git
cd acex
./setup.sh
```

Or with Taskfile:

```bash
task setup
```

The setup script will:

1. Add `127.0.0.1 keycloak` to `/etc/hosts` (requires `sudo`)
2. Create `.env` from `.env.example`
3. Clone `acex-frontend` into a sibling directory
4. Build all Docker images
5. Start the full stack
6. Seed mock devices, a collection agent, and a telemetry agent

!!! note "Why does setup need sudo?"
    The backend validates JWTs and expects the issuer claim to be `http://keycloak:8180/realms/acex`. Your browser needs to resolve `keycloak` to your machine so the issuer URL matches. Setup adds a single line to `/etc/hosts` — a one-time change that has no effect outside of ACE-X.

### Service URLs after startup

| Service  | URL | Default credentials |
|----------|-----|---------------------|
| ACE-X frontend | http://localhost:3000 | admin / admin |
| Backend API | http://localhost:8080 | — |
| Keycloak | http://keycloak:8180 | admin / admin |
| Grafana | http://localhost:3001 | admin / admin |
| InfluxDB | http://localhost:8086 | admin / adminpassword |

## Python packages only

Install individual packages without Docker:

```bash
# Core backend
pip install acex

# CLI (includes acex as a dependency)
pip install acex-cli

# Worker
pip install acex-worker

# MCP server for AI assistants
pip install acex-mcp-server
```

## NED drivers

NED drivers (Network Element Drivers) are separate packages that must be installed alongside the backend:

```bash
# Cisco IOS CLI driver
pip install acex-driver-cisco-ioscli

# Juniper JunOS CLI driver
pip install acex-driver-juniper-junoscli
```

Drivers are discovered automatically at startup via the `acex.neds` setuptools entry point group. Collection agents download and install missing NEDs automatically on startup.
