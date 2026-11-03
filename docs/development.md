# ACE-X Development Guide

## Prerequisites

- Python 3.13 or higher
- [Poetry](https://python-poetry.org/docs/#installation)
- Git

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/acex-labs/acex.git
   cd acex
   ```

2. **Run the development setup script:**
   ```bash
   ./scripts/dev-setup.sh
   ```

   This runs `poetry install` for devkit, backend, cli, worker and mcp and creates `.venv` in each of those package directories. The client and the drivers come in as path dependencies of them. To work on one of the others (an agent, a driver), run `poetry install` in its directory, for example `agents/collection-agent`.

3. **Activate a package environment:**
   ```bash
   cd backend && source .venv/bin/activate
   ```
   Each package has its own `.venv/` after setup. Switch by deactivating first:
   ```bash
   deactivate
   cd ../cli && source .venv/bin/activate
   ```

4. **Verify installation:**
   ```bash
   cd backend
   poetry run python -c "import acex; print(acex.__version__)"
   ```

## Project Structure

```
acex/
├── backend/             # acex: the API, the configuration model and its components
├── cli/                 # acex-cli
├── client/              # acex-client: API client used by the CLI, worker, MCP server and agents
├── devkit/              # acex-devkit: models shared by every package
├── worker/              # acex-worker: background jobs for the backend
├── mcp/                 # acex-mcp: MCP tool server
├── agents/
│   ├── collection-agent/
│   ├── telemetry-agent/
│   └── grafana-sync/
├── drivers/
│   ├── cisco_ios_cli/   # acex-driver-cisco-ioscli
│   └── juniper_junos_cli/   # acex-driver-juniper-junoscli
├── mock-device/         # SSH mock devices for the local stack
├── keycloak/            # realm for the local stack
├── scripts/             # dev-setup.sh, changelog.py, seed scripts
├── tests/integration/   # tests that span several packages
├── docs/                # this site
├── docker-compose.yml   # the local stack
└── Taskfile.yml         # tasks for the local stack
```

Each package has its own `pyproject.toml`, `src/` and, after setup, its own `.venv/`.

## Switching Between Package Environments

Each package has its own isolated `.venv`. To switch:

```bash
deactivate                               # leave current env
cd ../cli && source .venv/bin/activate   # enter another
```

Or just open a new terminal per package.

## Development Workflow

### Making Changes

All packages are installed in **editable mode** by Poetry, which means:
- Changes to code in `backend/src/`, `cli/src/`, or `worker/src/` are immediately available
- No need to reinstall after code changes
- Just restart your Python process or reimport to see changes

### Working on a Package

```bash
cd backend
source .venv/bin/activate
python               # changes in src/ are live (editable install)
pytest
```

### Running Examples

With env activated you can cd freely — the env stays active:
```bash
cd backend && source .venv/bin/activate
cd ../docs/examples/example1
python app.py
```

Or without activating:
```bash
cd backend
poetry run python ../docs/examples/example1/app.py
```

## Rebuilding Environment

If you need to rebuild the entire development environment:

```bash
./scripts/dev-setup.sh
```

This will run `poetry install` for all packages.

To clean and rebuild a specific package:
```bash
cd backend
rm -rf .venv
poetry install
```

## Package Dependencies

- `acex-devkit`: no internal dependencies. The models everything else shares.
- `acex-client` and the two drivers: depend on `acex-devkit`.
- `acex` (backend): depends on `acex-devkit`. The drivers are development dependencies, used by its tests.
- `acex-cli`: depends on `acex-client`, `acex-devkit` and the Cisco driver.
- `acex-worker`: depends on `acex-client` and `acex-devkit`.
- `acex-mcp` and the three agents: depend on `acex-client`.

In the repository these are local paths (`path = "../devkit"`, editable), so a change in devkit or client is live in every package that uses it. When a package is published, CI runs `switch_deps.sh prod` to replace the paths with version ranges (`^<major>`). You do not run it yourself, and the development images do not use it.

## Adding Dependencies

To add a dependency to a package:

```bash
cd backend
poetry add <package-name>

cd cli
poetry add <package-name>
```

## Testing

Each package has its own tests:

```bash
cd backend
poetry run pytest
```

Tests that span several packages are in `tests/integration`. On every pull request CI runs the lint and format checks, the unit tests of each package and the integration tests.

## Linting and Formatting

The repository uses [Ruff](https://docs.astral.sh/ruff/), configured in `ruff.toml` (line length 120):

```bash
ruff check .
ruff format .
```

The pre-commit hooks run the same checks. Install them with `pre-commit install`.

## Running the Full Stack

Everything (backend, frontend, agents, mock devices, Keycloak, Grafana, InfluxDB) runs with Docker Compose and `task setup`, described in [Installation](getting-started/installation.md). To run the API from source against the database of that stack, with authentication off and any origin allowed:

```bash
task api
```

## Branch Naming

All branches must follow the format `<prefix>/<description>` (Conventional Commits style):

- **Allowed prefixes:** `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `hotfix`, `ci`, `perf`, `build`
  (note: `feature` is not allowed — use `feat`)
- **Description:** lowercase letters, digits, and hyphens (kebab-case)

Examples: `feat/add-ntp-support`, `fix/static-route-nil-check`, `hotfix/1.2.1-crash-on-boot`

Exceptions: `main`, `stage`, `dev`, and `dependabot/*` are not validated.

The standard is enforced at three levels:

1. **Locally** — a pre-commit hook (`post-checkout`) warns immediately when you check out a branch with an invalid name. Enable with:
   ```bash
   pre-commit install --hook-type post-checkout
   ```
2. **CI** — the `Branch name policy` job in `.github/workflows/ci.yml` fails PRs from invalidly named branches.
3. **GitHub ruleset** (manual step, requires admin) — block creation of invalid branches on the server:
   - Go to **Settings → Rules → Rulesets → New ruleset → New branch ruleset**
   - **Enforcement status:** Active
   - **Targets:** Add target → Include all branches (or exclude `main`/`stage`)
   - Under **Branch rules**, enable **Restrict branch names** and add the patterns:
     - `feat/*`, `fix/*`, `chore/*`, `docs/*`, `refactor/*`, `test/*`, `hotfix/*`, `ci/*`, `perf/*`, `build/*`
     - plus `main` and `stage` (and optionally `dependabot/**`) if you included all branches
   - Save the ruleset.

The validation script used by both the hook and CI lives in `scripts/check_branch_name.sh` and can be run manually:

```bash
scripts/check_branch_name.sh              # validate the current branch
scripts/check_branch_name.sh fix/my-fix   # validate a given name
```

## Release Notes

Every pull request that changes a package adds a changelog fragment for it, a small file in the package's `changelog.d/` directory:

```bash
python scripts/changelog.py new backend --kind fixed --title "Static routes no longer fail on an empty next hop"
```

CI fails a pull request without one (`Changelog entry`). Use `--kind internal` for a change that users cannot notice. The fragments become the release notes under Settings > What's new when a release is cut. The format, the kinds and how a release is cut are in [Release notes](guides/changelog.md).

## Development Images

Every push to `dev` runs `.github/workflows/docker-dev.yml`, which publishes the backend, worker, agent and MCP images to the same GHCR repositories as a release, under development tags:

```
ghcr.io/acex-labs/acex-backend:dev              # moving: newest successful dev build
ghcr.io/acex-labs/acex-backend:dev-<short-sha>  # fixed: one commit
```

The same pattern applies to `acex-worker`, `acex-collection-agent`, `acex-telemetry-agent`, `acex-grafana-sync-agent` and `acex-mcp`. Development builds install devkit, client and the drivers from the checked-out source, so they always contain the code of the commit they were built from, even when no package version has been bumped. They never publish `latest`, upload to PyPI or create a release; that remains the `main` pipeline in `ci.yml`.

The six images are built independently. If one build fails, the others still receive the new tags and the failed image keeps its previous `dev` tag, so `:dev` can temporarily mix commits. The run summary lists, per image, whether `dev-<short-sha>` was published and its digest.

A `dev-<short-sha>` tag tells you which commit an image was built from, but tags are not immutable: a rebuild of the same commit (for example after a base image or dependency update) replaces it. When a deployment must be pinned to exactly one image, reference the digest from the run summary instead, e.g. `ghcr.io/acex-labs/acex-backend@sha256:…`.

## Env Files and Secrets

Files such as `.env`, `.env.<variant>`, and `*.env` may contain secrets and are never versioned. They are matched by `.gitignore`, and a pre-commit hook (`scripts/check_no_env_files.sh`) blocks commits that include them. Templates with placeholder values are checked in as `*.env.example`.

Note: `.gitignore` does not affect already-tracked files. To untrack a file that is already in git (while keeping it locally):

```bash
git rm --cached backend/.env
```

If a secret has accidentally ended up in history it must be rotated/invalidated — git-scrub does not remove it from old clones.

## Building for Distribution

To build a package:

```bash
cd backend
poetry build
```

The distribution files are in `dist/` of the package. Releases are published by CI from `main`; see [Release notes](guides/changelog.md).

## Tips

- Activate with `source .venv/bin/activate` (after `dev-setup.sh` has been run)
- Switch env: `deactivate && cd <pkg> && source .venv/bin/activate`
- One-off commands without activating: `cd backend && poetry run pytest`
- Changes in `src/` are immediately live — packages are installed in editable mode
- If you change `pyproject.toml`, run `poetry install` again in that package
