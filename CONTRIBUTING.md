# Contributing to ACE-X

Thank you for considering contributing to ACE-X!

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

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Add tests for your changes
4. Run tests to ensure they pass
5. Commit your changes: `git commit -m "Add your feature"`
6. Push to your fork: `git push origin feature/your-feature`
7. Create a Pull Request

### Versioning

When releasing new versions:

1. Update version in each affected package's `pyproject.toml`
2. Update version in each affected package's `__init__.py`
3. Update CHANGELOG.md
4. Tag the release: `git tag v0.2.0`

## Questions?

Feel free to open an issue for any questions or concerns.
