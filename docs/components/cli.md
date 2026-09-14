# CLI

The `acex-cli` package provides a command-line interface for interacting with a running ACE-X backend. It does not need the backend installed locally — all commands talk to the REST API.

## Install

```bash
pip install acex-cli
```

## Context management

The CLI manages named server profiles (contexts) so you can switch between ACE-X deployments:

```bash
acex context add prod --url https://acex.example.com
acex context use prod
acex context list
```

## Commands

### `acex asset`

Manage physical hardware assets.

```bash
acex asset list
acex asset show <id>
acex asset create --hostname rtr-01 --ned cisco-ios-cli ...
acex asset delete <id>
```

### `acex logical-node`

Manage logical node configuration templates.

```bash
acex logical-node list
acex logical-node show <id>
acex logical-node compile --all          # compile all nodes
acex logical-node compile --hostname rtr-01
```

### `acex ned`

List installed NED drivers and their capabilities.

```bash
acex ned list
acex ned show cisco-ios-cli
```

### `acex node`

The main operational command group for working with deployed node instances.

```bash
# List nodes with optional filters
acex node list
acex node list --site stockholm --role core

# Show details for one node
acex node show rtr-01

# Open an SSH session directly
acex node connect rtr-01
```

#### `acex node config`

```bash
# Show the vendor-agnostic desired config
acex node config show desired rtr-01

# Render it to Cisco IOS CLI
acex node config show desired rtr-01 --render

# Show the last collected running config
acex node config show observed rtr-01

# Compile and show from a local ConfigMap directory (no backend needed)
acex node config show local --dir ./config_maps --hostname rtr-01
```

#### `acex node config diff`

```bash
# Compute the diff between observed and desired
acex node config diff plan rtr-01

# Output formats: tree (default), compact, flat, summary, json, commands
acex node config diff plan rtr-01 --format commands

# Review and apply the patch
acex node config diff apply rtr-01
```

`diff apply` shows the generated patch commands and asks for confirmation before opening an SSH session.
