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
