# Quick Start

This guide walks through the core workflow: write a ConfigMap, compile it, and inspect the rendered output against a mock device.

## Prerequisites

A running ACE-X stack. See [Installation](installation.md) — the `task setup` command starts everything including five mock SSH devices.

## 1. Write a ConfigMap

A ConfigMap is a Python class with a `compile(context)` method. Create a file `config_maps/loopback.py`:

```python
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Loopback


class LoopbackIf(ConfigMap):
    def compile(self, context):
        lo0 = Loopback(
            index=0,
            name="Lo0",
            description="MPLS Loopback",
            ipv4=f"192.0.2.{context.logical_node.id}/24",
        )
        context.configuration.add(lo0)


# Apply to all nodes with role == core
lo = LoopbackIf()
lo.filters = FilterAttribute("role").eq("core")
```

## 2. Register ConfigMaps with the engine

```python
from acex import AutomationEngine

# dev_mode serves without authentication, for local work only. A deployment
# configures an OIDC issuer with ae.set_oidc(...) instead.
ae = AutomationEngine(dev_mode=True)
ae.add_configmap_dir("./config_maps")
app = ae.create_app()
```

## 3. Compile

```bash
# Trigger a compile for all logical nodes
acex logical-node compile --all

# Or compile a specific node
acex logical-node compile --hostname core-rtr-01
```

## 4. Inspect the desired config

```bash
# Show the vendor-agnostic configuration model
acex node config show desired core-rtr-01

# Render it to Cisco IOS CLI
acex node config show desired core-rtr-01 --render
```

## 5. Diff against observed config

```bash
# Show what would change on the device
acex node config diff plan core-rtr-01

# Output formats: tree (default), compact, flat, summary, json, commands
acex node config diff plan core-rtr-01 --format commands
```

## 6. Apply

```bash
# Review the patch commands and confirm
acex node config diff apply core-rtr-01
```

ACE-X will show the generated CLI commands and ask for confirmation before opening an SSH connection to the device.

## Daily workflow commands

```bash
task up       # start the stack
task down     # stop the stack
task logs     # tail all logs
task seed     # re-seed mock devices (idempotent)
task reset    # wipe everything and re-run setup
```
