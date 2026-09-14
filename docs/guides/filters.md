# Filters

Filters control which logical nodes receive a ConfigMap. A ConfigMap without filters applies to all nodes.

## FilterAttribute

```python
from acex.config_map import FilterAttribute

# Apply to all nodes with role == core
lo.filters = FilterAttribute("role").eq("core")

# Apply to all nodes at site hq
lo.filters = FilterAttribute("site").eq("hq")

# Combine filters (AND)
lo.filters = FilterAttribute("site").eq("hq") & FilterAttribute("role").eq("core")
```

## Operators

| Method | Meaning |
|--------|---------|
| `.eq(value)` | attribute equals value |
| `.ne(value)` | attribute does not equal value |
| `.contains(value)` | attribute contains value (substring) |
| `.startswith(value)` | attribute starts with value |

## Filterable attributes

Filters match against attributes of the `LogicalNode` object:

| Attribute | Description |
|-----------|-------------|
| `role` | Node role (e.g., `core`, `access`, `distribution`) |
| `site` | Site identifier |
| `hostname` | Hostname |
| `sequence` | Sequence number within a group |

## Examples

```python
# All core nodes everywhere
ntp.filters = FilterAttribute("role").eq("core")

# All access nodes at site stockholm
stp.filters = FilterAttribute("role").eq("access") & FilterAttribute("site").eq("stockholm")

# A specific node by hostname
banner.filters = FilterAttribute("hostname").eq("core-rtr-01")

# No filter — applies to all nodes
mgmt.filters = None
```
