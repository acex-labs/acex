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

Alla branches måste följa formatet `<prefix>/<description>` (Conventional Commits-stil):

- **Tillåtna prefix:** `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `hotfix`, `ci`, `perf`, `build`
  (observera: `feature` är inte tillåtet — använd `feat`)
- **Description:** gemener, siffror och bindestreck (kebab-case)

Exempel: `feat/add-ntp-support`, `fix/static-route-nil-check`, `hotfix/1.2.1-crash-on-boot`

Undantag: `main`, `stage` och `dependabot/*` valideras inte.

Standarden enforcas på tre nivåer:

1. **Lokalt** — en pre-commit-hook (`post-checkout`) varnar direkt när du checkar ut en branch med ogiltigt namn. Aktivera med:
   ```bash
   pre-commit install --hook-type post-checkout
   ```
2. **CI** — jobbet `Branch name policy` i `.github/workflows/ci.yml` failar PR:s från ogiltigt namngivna branches.
3. **GitHub ruleset** (manuellt steg, kräver admin) — blockera skapande av felaktiga branches redan på servern:
   - Gå till **Settings → Rules → Rulesets → New ruleset → New branch ruleset**
   - **Enforcement status:** Active
   - **Targets:** Add target → Include all branches (eller exkludera `main`/`stage`)
   - Under **Branch rules**, aktivera **Restrict branch names** och lägg till mönstren:
     - `feat/*`, `fix/*`, `chore/*`, `docs/*`, `refactor/*`, `test/*`, `hotfix/*`, `ci/*`, `perf/*`, `build/*`
     - samt `main` och `stage` (och ev. `dependabot/**`) om du inkluderade alla branches
   - Spara rulesetet.

Valideringsskriptet som används av både hooken och CI ligger i `scripts/check_branch_name.sh` och kan köras manuellt:

```bash
scripts/check_branch_name.sh              # validera nuvarande branch
scripts/check_branch_name.sh fix/my-fix   # validera ett givet namn
```

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
