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

3. **Work on a specific package:**
   
   **Poetry 2.0+** (recommended):
   ```bash
   # Backend
   cd backend
   source $(poetry env info --path)/bin/activate
   
   # CLI
   cd cli
   source $(poetry env info --path)/bin/activate
   
   # Worker
   cd worker
   source $(poetry env info --path)/bin/activate
   ```
   
   **Or install the shell plugin** (optional):
   ```bash
   poetry self add poetry-plugin-shell
   cd backend
   poetry shell
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
│   ├── src/acex/    # Source code
│   └── pyproject.toml
├── cli/             # CLI package (acex-cli)
│   ├── .venv/       # CLI virtual environment
│   ├── src/acex_cli/
│   └── pyproject.toml
└── worker/          # Worker package (acex-worker)
    ├── .venv/       # Worker virtual environment
    ├── src/acex_worker/
    └── pyproject.toml
```

## Development Workflow

### Making Changes

All packages are installed in **editable mode** by Poetry, which means:
- Changes to code in `backend/src/`, `cli/src/`, or `worker/src/` are immediately available
- No need to reinstall after code changes
- Just restart your Python process or reimport to see changes

### Working on Backend

**Activate the environment:**
```bash
cd backend
source $(poetry env info --path)/bin/activate
python               # Your changes are live!
```

**Or use poetry run without activating:**
```bash
cd backend
poetry run python
poetry run pytest
```

### Working on CLI

```bash
cd cli
source $(poetry env info --path)/bin/activate
python -c "import acex_cli; import acex"  # Both available
```

### Running Examples

From the backend environment:
```bash
cd backend
poetry run python ../docs/examples/example1/app.py
```

Or activate the environment first:
```bash
cd backend
source $(poetry env info --path)/bin/activate
cd ../docs/examples/example1
python app.py
```

### Running Commands Without Shell

You can run commands without activating the shell:
```bash
cd backend
poetry run python script.py
poetry run pytest
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

- Use `source $(poetry env info --path)/bin/activate` to activate the environment (Poetry 2.0+)
- Or use `poetry run <command>` for one-off commands without activating
- Install `poetry-plugin-shell` if you prefer the old `poetry shell` command
- Changes in `backend/src/` are immediately visible in `cli` and `worker` (editable mode)
- If you change `pyproject.toml`, run `poetry install` again
