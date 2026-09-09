# Contributing to ACE-X

Thank you for considering contributing to ACE-X!

## Local Development Environment (Docker)

The fastest way to run a full ACEX stack locally — backend, frontend, agents, mock network devices, Grafana, Keycloak, InfluxDB — is with Docker Compose and the provided setup script.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose v2)
- Git
- [`task`](https://taskfile.dev/#/installation) (optional but recommended — `brew install go-task`)

### One-command setup

```bash
git clone git@github.com:acex-labs/acex.git
cd acex
./setup.sh
```

Or with Taskfile:

```bash
task setup
```

The script will:

1. Add `127.0.0.1 keycloak` to `/etc/hosts` — **this requires a `sudo` prompt** (see below)
2. Create `.env` from `.env.example`
3. Clone `acex-frontend` into `../acex-frontend` (sibling of this repo)
4. Build all Docker images
5. Start the full stack
6. Seed mock devices, a collection agent, and a telemetry agent — and write their IDs back to `.env`

### Why does setup need sudo?

ACEX uses Keycloak for authentication. The backend validates JWTs and expects the issuer claim to be `http://keycloak:8180/realms/acex`. For this to work, your browser also needs to reach Keycloak at that same hostname — not `localhost`.

The setup script adds a single line to your system hosts file:

```
127.0.0.1 keycloak
```

This makes `keycloak` resolve to your own machine, so the browser, the backend, and the Docker containers all agree on the issuer URL. It is a one-time change and does not affect anything outside of ACEX.

If you prefer to add it manually instead of granting sudo:

```bash
echo "127.0.0.1 keycloak" | sudo tee -a /etc/hosts
```

### URLs after startup

| Service  | URL                              | Default credentials |
|----------|----------------------------------|---------------------|
| ACEX     | http://localhost:3000            | admin / admin       |
| Backend  | http://localhost:8080            | —                   |
| Keycloak | http://keycloak:8180             | admin / admin       |
| Grafana  | http://localhost:3001            | admin / admin       |
| InfluxDB | http://localhost:8086            | admin / adminpassword |

> Keycloak can take ~30 seconds to finish importing the realm on the very first boot.

### Daily workflow

```bash
task up          # start the stack
task down        # stop the stack
task logs        # tail all logs  (task logs -- backend  for one service)
task restart -- frontend   # restart a single service after a code change
task build -- frontend     # rebuild one image
task ps          # see what's running
```

### Re-seeding / resetting

If you add devices or want to reprovisioning agents:

```bash
task seed        # idempotent — safe to run any time
```

To wipe everything and start from scratch:

```bash
task reset       # tears down all containers and volumes, then re-runs setup
```

---

## Development Setup

### Prerequisites

- Python 3.13+
- Poetry

### Setting Up the Development Environment

ACE-X is a monorepo with multiple packages. You can work on individual packages:

```bash
# Clone the repository
git clone https://github.com/acex-labs/acex.git
cd acex

# Set up backend
cd backend
poetry install
poetry run pytest

# Set up CLI
cd ../cli
poetry install

# Set up worker
cd ../worker
poetry install
```

### Running Tests

Each package has its own test suite:

```bash
# Backend tests
cd backend
poetry run pytest

# CLI tests
cd cli
poetry run pytest

# Worker tests
cd worker
poetry run pytest
```

### Code Style

We use `ruff` for linting and formatting:

```bash
# Install ruff
pip install ruff

# Format code
ruff format .

# Lint
ruff check .
```

### Making Changes

1. Create a branch following the naming convention (`<prefix>/<description>`, Conventional Commits style — see DEVELOPMENT.md): `git checkout -b feat/your-feature`
2. Make your changes
3. Add tests for your changes
4. Run tests to ensure they pass
5. Commit your changes: `git commit -m "Add your feature"`
6. Push to your fork: `git push origin feat/your-feature`
7. Create a Pull Request

### Versioning

When releasing new versions:

1. Update version in each affected package's `pyproject.toml`
2. Update version in each affected package's `__init__.py`
3. Update CHANGELOG.md
4. Tag the release: `git tag v0.2.0`

## Questions?

Feel free to open an issue for any questions or concerns.
