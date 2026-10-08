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

   This installs all packages using Poetry and creates `.venv` in each package directory.

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
├── backend/          # Core backend package (acex)
│   ├── .venv/       # Backend virtual environment
│   ├── src/acex/
│   └── pyproject.toml
├── cli/             # CLI package (acex-cli)
│   ├── .venv/
│   ├── src/acex_cli/
│   └── pyproject.toml
├── worker/          # Worker package (acex-worker)
│   ├── .venv/
│   ├── src/acex_worker/
│   └── pyproject.toml
├── mcp/             # MCP server (acex-mcp-server)
│   ├── .venv/
│   └── pyproject.toml
└── devkit/          # Shared models (acex-devkit)
    ├── .venv/
    └── pyproject.toml
```

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

- `acex` (backend) - No internal dependencies
- `acex-cli` - Depends on `acex` (via `path = "../backend"`)
- `acex-worker` - Depends on `acex` (via `path = "../backend"`)

The dependencies use local paths during development, so changes in backend are immediately available in CLI and Worker.

## Adding Dependencies

To add a dependency to a package:

```bash
cd backend
poetry add <package-name>

cd cli
poetry add <package-name>
```

## Testing

```bash
cd backend
poetry run pytest

cd cli
poetry run pytest
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

## Development Images

Every push to `dev` runs `.github/workflows/docker-dev.yml`, which publishes the backend, agent and MCP images to the same GHCR repositories as a release, under development tags:

```
ghcr.io/acex-labs/acex-backend:dev              # moving: newest successful dev build
ghcr.io/acex-labs/acex-backend:dev-<short-sha>  # fixed: one commit
```

The same pattern applies to `acex-collection-agent`, `acex-telemetry-agent`, `acex-grafana-sync-agent` and `acex-mcp`. Development builds install devkit, client and the drivers from the checked-out source, so they always contain the code of the commit they were built from, even when no package version has been bumped. They never publish `latest`, upload to PyPI or create a release; that remains the `main` pipeline in `ci.yml`.

The five images are built independently. If one build fails, the others still receive the new tags and the failed image keeps its previous `dev` tag, so `:dev` can temporarily mix commits. The run summary lists, per image, whether `dev-<short-sha>` was published and its digest.

A `dev-<short-sha>` tag tells you which commit an image was built from, but tags are not immutable: a rebuild of the same commit (for example after a base image or dependency update) replaces it. When a deployment must be pinned to exactly one image, reference the digest from the run summary instead, e.g. `ghcr.io/acex-labs/acex-backend@sha256:…`.

## Env Files and Secrets

Files such as `.env`, `.env.<variant>`, and `*.env` may contain secrets and are never versioned. They are matched by `.gitignore`, and a pre-commit hook (`scripts/check_no_env_files.sh`) blocks commits that include them. Templates with placeholder values are checked in as `*.env.example`.

Note: `.gitignore` does not affect already-tracked files. To untrack a file that is already in git (while keeping it locally):

```bash
git rm --cached backend/.env
```

If a secret has accidentally ended up in history it must be rotated/invalidated — git-scrub does not remove it from old clones.

## Building for Distribution

To build individual packages:

```bash
cd backend
poetry build

cd cli
poetry build

cd worker
poetry build
```

Distribution files will be in `dist/` folder of each package.

## Tips

- Activate with `source .venv/bin/activate` (after `dev-setup.sh` has been run)
- Switch env: `deactivate && cd <pkg> && source .venv/bin/activate`
- One-off commands without activating: `cd backend && poetry run pytest`
- Changes in `src/` are immediately live — packages are installed in editable mode
- If you change `pyproject.toml`, run `poetry install` again in that package
