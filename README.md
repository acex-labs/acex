# ACE-X - Automation & Control Ecosystem

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

ACE-X is an extendable automation and control ecosystem designed for building robust, distributed automation workflows.

## 🚀 Features

- **Modular Architecture** - Install only what you need
- **Distributed Execution** - Scale with worker nodes
- **CLI Tools** - Powerful command-line interface
- **API-First** - RESTful API for all operations
- **Plugin System** - Extend functionality with plugins

## 📦 Packages

ACE-X is organized as a monorepo with multiple installable packages:

| Package | Description | Installation |
|---------|-------------|--------------|
| [**acex**](./backend/) | Core backend and API | `pip install acex` |
| [**acex-cli**](./cli/) | Command-line interface | `pip install acex-cli` |
| [**acex-worker**](./worker/) | Distributed task worker | `pip install acex-worker` |

## 🔧 Installation

### Quick Start - Full Installation

```bash
# Install all components
pip install acex acex-cli acex-worker
```

### Minimal Installation

```bash
# Just the core
pip install acex

# Core + CLI
pip install acex-cli  # This includes acex as a dependency

# Core + Worker
pip install acex-worker  # This includes acex as a dependency
```

## 🎯 Quick Example

```python
from acex.core import AutomationEngine

# Initialize the engine
engine = AutomationEngine()

# Your automation code here
```

Using the CLI:

```bash
# Run an automation
acex run my_automation.py

# Check status
acex status

# List automations
acex list
```

## 🏗️ Development

This is a monorepo. Each package can be developed independently:

```bash
# Backend development
cd backend
poetry install
poetry run pytest

# CLI development
cd cli
poetry install

# Worker development
cd worker
poetry install
```

## 📚 Documentation

- [Backend Documentation](./backend/README.md)
- [CLI Documentation](./cli/README.md)
- [Worker Documentation](./worker/README.md)

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 👤 Author

Johan Lahti <johan.lahti@acebit.se>

## 🔗 Links

- Repository: https://github.com/acex-labs/acex
- Issues: https://github.com/acex-labs/acex/issues