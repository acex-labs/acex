# ACE-X CLI

Command-line interface for managing ACE-X automations.

## Installation

```bash
pip install acex-cli
```

This will also install the `acex` backend package as a dependency.

## Development

```bash
cd cli
poetry install
```

## Usage

```bash
acex --help
acex run automation.py
acex list
acex status
```

## Commands

- `acex run` - Run an automation
- `acex list` - List available automations
- `acex status` - Check system status
- `acex config` - Manage configuration

## Documentation

See the [main documentation](../README.md) for more information.
