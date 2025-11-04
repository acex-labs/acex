# ACE-X - Automation & Control Ecosystem

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
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

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)** - see the [LICENSE](LICENSE) file for details.

### What does AGPL mean?

- ✅ **Free to use** - Use ACE-X for any purpose
- ✅ **Open source** - Full source code available
- ✅ **Modify freely** - Change and adapt as needed
- ⚠️ **Share modifications** - If you modify and run ACE-X as a network service, you must share your modifications
- ⚠️ **Same license** - Derivative works must also be AGPL-licensed

### Dual Licensing

**Commercial licenses** are available for organizations that wish to use ACE-X without the obligations of the AGPL.

For commercial licensing inquiries, contact: **license@acex.dev**

**Why AGPL?**

The AGPL license ensures that improvements to ACE-X benefit the entire community, even when the software is used to provide network services. If you run a modified version of ACE-X as a service, users of that service can request the source code.

## 👤 Author

Johan Lahti <johan.lahti@acebit.se>

## 🔗 Links

- Repository: https://github.com/acex-labs/acex
- Issues: https://github.com/acex-labs/acex/issues