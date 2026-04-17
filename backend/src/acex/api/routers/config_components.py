"""
Config Components Library API Router.

Provides introspection of available configuration components
and Python code generation for ConfigMap files.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import (
    List, Optional, Dict, Any, Union, Literal,
    get_args, get_origin,
)
from types import NoneType
from enum import Enum
import re

from acex.constants import BASE_URL
from acex.configuration.configuration import Configuration
from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models import AttributeValue


# ── Response / Request Models ─────────────────────────────────────


class FieldInfo(BaseModel):
    name: str
    type: str  # "string", "integer", "boolean", "list[integer]", "enum", "reference"
    required: bool = False
    description: Optional[str] = None
    enum_values: Optional[List[str]] = None
    is_reference: bool = False
    reference_target: Optional[str] = None


class ComponentInfo(BaseModel):
    name: str
    type: str
    category: str
    description: str
    import_module: str
    fields: List[FieldInfo]


class ComponentCatalog(BaseModel):
    components: List[ComponentInfo]


class ComponentInstance(BaseModel):
    component: str
    variable_name: str
    values: Dict[str, Any]


class FilterSpec(BaseModel):
    attribute: str = "role"
    operator: str = "eq"
    value: str = "/.*/"


class GenerateRequest(BaseModel):
    class_name: str = "MyConfigMap"
    filter: Optional[FilterSpec] = None
    components: List[ComponentInstance]


class GenerateResponse(BaseModel):
    code: str


class ReconcileOptions(BaseModel):
    class_name: str = "ReconcileConfigMap"
    filter: Optional[FilterSpec] = None
    mode: Literal["diff", "full"] = "diff"
    # Only used in diff mode:
    include_removed: bool = True
    include_changed: bool = True


# ── Component metadata ────────────────────────────────────────────

DESCRIPTIONS = {
    "HostName": "Set the device hostname",
    "Contact": "Set system contact information",
    "Location": "Set system location",
    "DomainName": "Set the domain name",
    "LoginBanner": "Set the login banner message",
    "MotdBanner": "Set the message-of-the-day banner",
    "NtpServer": "Configure an NTP server",
    "SshServer": "Configure SSH server settings",
    "AuthorizedKey": "Add an SSH authorized key",
    "FrontpanelPort": "Configure a physical Ethernet interface",
    "ManagementPort": "Configure a management interface",
    "Loopback": "Configure a loopback interface",
    "Svi": "Configure a VLAN interface (SVI)",
    "LagInterface": "Configure a LAG / port-channel interface",
    "Subinterface": "Configure a sub-interface",
    "L3Vrf": "Create a Layer 3 VRF network instance",
    "L2Domain": "Create a Layer 2 bridge domain",
    "NetworkInstance": "Create a network instance (prefer L3Vrf)",
    "Vlan": "Configure a VLAN",
    "StaticRoute": "Configure a static route",
    "StaticRouteNextHop": "Configure a next-hop for a static route",
    "Ipv4Acl": "Create an IPv4 access control list",
    "Ipv4AclEntry": "Add an entry to an IPv4 ACL",
    "Ipv6Acl": "Create an IPv6 access control list",
    "Ipv6AclEntry": "Add an entry to an IPv6 ACL",
    "LacpConfig": "Configure global LACP settings",
    "SpanningTreeGlobal": "Configure global Spanning Tree settings",
    "SpanningTreeRSTP": "Configure Rapid Spanning Tree Protocol",
    "SpanningTreeMSTP": "Configure Multiple Spanning Tree Protocol",
    "SpanningTreeMstpInstance": "Configure an MST instance",
    "SpanningTreeRapidPVST": "Configure Rapid Per-VLAN Spanning Tree",
    "LoggingConfig": "Configure global logging settings",
    "Console": "Configure console logging",
    "VtyLine": "Configure VTY line logging",
    "RemoteServer": "Configure a remote syslog server",
    "FileLogging": "Configure file-based logging",
    "SnmpGlobal": "Configure global SNMP settings",
    "SnmpUser": "Configure an SNMP user (SNMPv3)",
    "SnmpServer": "Configure an SNMP trap server",
    "SnmpTrap": "Configure an SNMP trap event",
    "SnmpCommunity": "Configure an SNMP community (SNMPv2c)",
    "aaaGlobal": "Enable or disable AAA globally",
    "aaaServerGroup": "Configure an AAA server group",
    "aaaTacacs": "Configure a TACACS+ server",
    "aaaRadius": "Configure a RADIUS server",
    "aaaAuthenticationMethods": "Configure AAA authentication method",
    "aaaAuthorizationMethods": "Configure AAA authorization method",
    "aaaAuthorizationEvents": "Configure AAA authorization event type",
    "aaaAccountingMethods": "Configure AAA accounting method",
    "aaaAccountingEvents": "Configure AAA accounting event type",
}

# Import path overrides — only needed when cls.__module__ doesn't match
# the user-facing import (e.g. re-exports via __init__.py).
# For most components, __module__ is resolved automatically.
IMPORT_MAP_OVERRIDES = {
    "HostName": "acex.configuration.components.system",
    "Contact": "acex.configuration.components.system",
    "Location": "acex.configuration.components.system",
    "DomainName": "acex.configuration.components.system",
    "LoginBanner": "acex.configuration.components.system",
    "MotdBanner": "acex.configuration.components.system",
    "NtpServer": "acex.configuration.components.system.ntp",
    "SshServer": "acex.configuration.components.system.ssh",
    "AuthorizedKey": "acex.configuration.components.system.ssh",
    "LoggingConfig": "acex.configuration.components.system.logging",
    "Console": "acex.configuration.components.system.logging",
    "VtyLine": "acex.configuration.components.system.logging",
    "RemoteServer": "acex.configuration.components.system.logging",
    "FileLogging": "acex.configuration.components.system.logging",
    "SnmpGlobal": "acex.configuration.components.system.snmp",
    "SnmpUser": "acex.configuration.components.system.snmp",
    "SnmpServer": "acex.configuration.components.system.snmp",
    "SnmpTrap": "acex.configuration.components.system.snmp",
    "SnmpCommunity": "acex.configuration.components.system.snmp",
    "aaaGlobal": "acex.configuration.components.system.aaa",
    "aaaServerGroup": "acex.configuration.components.system.aaa",
    "aaaTacacs": "acex.configuration.components.system.aaa",
    "aaaRadius": "acex.configuration.components.system.aaa",
    "aaaAuthenticationMethods": "acex.configuration.components.system.aaa",
    "aaaAuthorizationMethods": "acex.configuration.components.system.aaa",
    "aaaAuthorizationEvents": "acex.configuration.components.system.aaa",
    "aaaAccountingMethods": "acex.configuration.components.system.aaa",
    "aaaAccountingEvents": "acex.configuration.components.system.aaa",
    "FrontpanelPort": "acex.configuration.components.interfaces",
    "ManagementPort": "acex.configuration.components.interfaces",
    "Loopback": "acex.configuration.components.interfaces",
    "Svi": "acex.configuration.components.interfaces",
    "LagInterface": "acex.configuration.components.interfaces",
    "Subinterface": "acex.configuration.components.interfaces",
    "L3Vrf": "acex.configuration.components.network_instances",
    "L2Domain": "acex.configuration.components.network_instances",
    "NetworkInstance": "acex.configuration.components.network_instances",
    "Vlan": "acex.configuration.components.vlan",
    "StaticRoute": "acex.configuration.components.routing",
    "StaticRouteNextHop": "acex.configuration.components.routing",
    "Ipv4Acl": "acex.configuration.components.acl",
    "Ipv6Acl": "acex.configuration.components.acl",
    "Ipv4AclEntry": "acex.configuration.components.acl",
    "Ipv6AclEntry": "acex.configuration.components.acl",
    "LacpConfig": "acex.configuration.components.lacp",
    "SpanningTreeGlobal": "acex.configuration.components.spanning_tree",
    "SpanningTreeRSTP": "acex.configuration.components.spanning_tree",
    "SpanningTreeMSTP": "acex.configuration.components.spanning_tree",
    "SpanningTreeMstpInstance": "acex.configuration.components.spanning_tree",
    "SpanningTreeRapidPVST": "acex.configuration.components.spanning_tree",
}

# Fields that accept component object references.
# Synthetic fields (not in model_cls) are added to the catalog automatically.
REFERENCE_FIELDS = {
    "FrontpanelPort": {
        "network_instance": {"target": "L3Vrf", "description": "VRF to assign interface to"},
    },
    "ManagementPort": {
        "network_instance": {"target": "L3Vrf", "description": "VRF to assign interface to"},
    },
    "Loopback": {
        "network_instance": {"target": "L3Vrf", "description": "VRF to assign interface to"},
    },
    "Svi": {
        "network_instance": {"target": "L3Vrf", "description": "VRF to assign interface to"},
        "vlan": {"target": "Vlan", "description": "VLAN to create SVI for"},
    },
    "Subinterface": {
        "network_instance": {"target": "L3Vrf", "description": "VRF to assign interface to"},
        "vlan": {"target": "Vlan", "description": "VLAN for sub-interface"},
    },
    "SshServer": {
        "source_interface": {"target": "Interface", "description": "Source interface for SSH"},
    },
    "Vlan": {
        "network_instance": {"target": "L3Vrf", "description": "Network instance for VLAN"},
    },
    "StaticRoute": {
        "network_instance": {"target": "L3Vrf", "description": "VRF for the static route"},
    },
    "StaticRouteNextHop": {
        "network_instance": {"target": "L3Vrf", "description": "VRF for the next-hop"},
        "static_route": {"target": "StaticRoute", "description": "Parent static route"},
    },
    "Ipv4AclEntry": {
        "ipv4_acl": {"target": "Ipv4Acl", "description": "Parent IPv4 ACL"},
    },
    "Ipv6AclEntry": {
        "ipv6_acl": {"target": "Ipv6Acl", "description": "Parent IPv6 ACL"},
    },
    "aaaTacacs": {
        "source_interface": {"target": "Interface", "description": "Source interface"},
        "server_group": {"target": "aaaServerGroup", "description": "Server group membership"},
    },
    "aaaRadius": {
        "source_interface": {"target": "Interface", "description": "Source interface"},
        "server_group": {"target": "aaaServerGroup", "description": "Server group membership"},
    },
    "SnmpCommunity": {
        "source_interface": {"target": "Interface", "description": "Source interface"},
    },
    "SnmpServer": {
        "source_interface": {"target": "Interface", "description": "Source interface"},
        "network_instance": {"target": "L3Vrf", "description": "VRF for trap server"},
    },
}

# Runtime lookup: component class name → resolved import module
_IMPORT_CACHE: Dict[str, str] = {}


def _resolve_import(cls) -> str:
    """
    Resolve the import module for a component class.
    Uses IMPORT_MAP_OVERRIDES if present, otherwise cls.__module__.
    """
    name = cls.__name__
    if name in _IMPORT_CACHE:
        return _IMPORT_CACHE[name]
    module = IMPORT_MAP_OVERRIDES.get(name, cls.__module__)
    _IMPORT_CACHE[name] = module
    return module


# Model fields to skip during introspection
SKIP_FIELDS = {
    "metadata", "type", "subinterfaces",
    "acl_entries", "tacacs", "radius", "next_hops",
}


# ── Introspection helpers ─────────────────────────────────────────


def _unwrap_attribute_value(annotation):
    """
    Unwrap Optional[AttributeValue[T]] and return (inner_type, is_optional).
    Returns (None, is_optional) if not an AttributeValue field.
    """
    is_optional = False
    inner = annotation

    origin = get_origin(inner)
    if origin is Union:
        args = get_args(inner)
        non_none = [a for a in args if a is not NoneType]
        if NoneType in args and len(non_none) == 1:
            is_optional = True
            inner = non_none[0]

    # Check via get_origin (standard generics)
    origin = get_origin(inner)
    is_av = (
        origin is AttributeValue
        or (origin is not None and getattr(origin, "__name__", "") == "AttributeValue")
    )
    if is_av:
        args = get_args(inner)
        return (args[0] if args else str), is_optional

    # Pydantic-generated subclass: AttributeValue[int] is a real class
    # that subclasses AttributeValue, with get_origin() returning None.
    if isinstance(inner, type) and issubclass(inner, AttributeValue):
        # Extract T from the model's 'value' field annotation
        if hasattr(inner, "model_fields") and "value" in inner.model_fields:
            value_ann = inner.model_fields["value"].annotation
            # Unwrap Union[T, ExternalValue] → T
            v_origin = get_origin(value_ann)
            if v_origin is Union:
                v_args = [a for a in get_args(value_ann)
                          if not (isinstance(a, type) and a.__name__ == "ExternalValue")]
                return (v_args[0] if v_args else str), is_optional
            return value_ann, is_optional
        return str, is_optional

    return None, is_optional


def _type_label(t) -> str:
    """Human-readable label for a Python type."""
    if t is str:
        return "string"
    if t is int:
        return "integer"
    if t is bool:
        return "boolean"
    if t is float:
        return "float"

    origin = get_origin(t)
    if origin is list or (isinstance(origin, type) and issubclass(origin, list)):
        args = get_args(t)
        return f"list[{_type_label(args[0])}]" if args else "list"
    if origin is Literal:
        return "enum"
    if origin is Union:
        return "string"
    if isinstance(t, type) and issubclass(t, Enum):
        return "enum"
    return getattr(t, "__name__", str(t))


def _enum_values(t) -> Optional[List[str]]:
    """Extract enum choices from a type, if any."""
    origin = get_origin(t)
    if origin is Literal:
        return [str(v) for v in get_args(t)]
    if isinstance(t, type) and issubclass(t, Enum):
        return [e.value for e in t]
    if origin is Union:
        for arg in get_args(t):
            vals = _enum_values(arg)
            if vals:
                return vals
    return None


def _introspect_fields(component_cls) -> List[FieldInfo]:
    """Extract field metadata from a component's Pydantic model."""
    model_cls = getattr(component_cls, "model_cls", None)
    if model_cls is None:
        return []

    fields = []
    name = component_cls.__name__
    refs = REFERENCE_FIELDS.get(name, {})
    seen = set()

    for field_name, finfo in model_cls.model_fields.items():
        if field_name in SKIP_FIELDS:
            continue
        seen.add(field_name)

        inner_type, is_optional = _unwrap_attribute_value(finfo.annotation)

        if inner_type is None:
            if field_name in refs:
                r = refs[field_name]
                fields.append(FieldInfo(
                    name=field_name,
                    type="reference",
                    required=not is_optional,
                    is_reference=True,
                    reference_target=r["target"],
                    description=r["description"],
                ))
            continue

        is_ref = field_name in refs
        label = _type_label(inner_type)

        fields.append(FieldInfo(
            name=field_name,
            type="reference" if is_ref else label,
            required=not is_optional and finfo.is_required(),
            description=refs[field_name]["description"] if is_ref else None,
            enum_values=_enum_values(inner_type) if label == "enum" else None,
            is_reference=is_ref,
            reference_target=refs[field_name]["target"] if is_ref else None,
        ))

    # Synthetic reference fields (not in model_cls but accepted by constructor)
    for ref_name, ref_info in refs.items():
        if ref_name not in seen:
            fields.append(FieldInfo(
                name=ref_name,
                type="reference",
                required=False,
                is_reference=True,
                reference_target=ref_info["target"],
                description=ref_info["description"],
            ))

    return fields


# ── Catalog builder ───────────────────────────────────────────────


def _build_catalog() -> ComponentCatalog:
    components = []
    seen = set()

    for cls in Configuration.COMPONENT_MAPPING:
        if not (isinstance(cls, type) and issubclass(cls, ConfigComponent)):
            continue

        name = cls.__name__
        if name in seen:
            continue
        seen.add(name)

        module = _resolve_import(cls)
        parts = module.split(".")
        try:
            idx = parts.index("components")
            category = parts[idx + 1] if idx + 1 < len(parts) else "other"
        except ValueError:
            category = "other"

        components.append(ComponentInfo(
            name=name,
            type=getattr(cls, "type", "component"),
            category=category,
            description=DESCRIPTIONS.get(name, f"{name} configuration component"),
            import_module=module,
            fields=_introspect_fields(cls),
        ))

    components.sort(key=lambda c: (c.category, c.name))
    return ComponentCatalog(components=components)


_catalog: Optional[ComponentCatalog] = None


def list_components() -> ComponentCatalog:
    """Return catalog of all available configuration components."""
    global _catalog
    if _catalog is None:
        _catalog = _build_catalog()
    return _catalog


# ── Code generation ───────────────────────────────────────────────


def _fmt(value: Any) -> str:
    """Format a value for Python source code."""
    if isinstance(value, str) and value.startswith("$"):
        return value[1:]
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return repr(value)
    return repr(value)


def _to_snake_case(name: str) -> str:
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()


def _component_class_by_name(name: str):
    """Look up a ConfigComponent class by name from COMPONENT_MAPPING."""
    for cls in Configuration.COMPONENT_MAPPING:
        if isinstance(cls, type) and cls.__name__ == name:
            return cls
    return None


def generate_configmap(request: GenerateRequest) -> GenerateResponse:
    """Generate a ConfigMap Python file from component specifications."""

    # Validate component names and collect classes
    component_classes: Dict[str, type] = {}
    for ci in request.components:
        cls = _component_class_by_name(ci.component)
        if cls is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown component: {ci.component}",
            )
        component_classes[ci.component] = cls

    # Collect imports grouped by module
    module_imports: Dict[str, set] = {
        "acex.config_map": {"ConfigMap", "FilterAttribute"},
    }
    for ci in request.components:
        mod = _resolve_import(component_classes[ci.component])
        module_imports.setdefault(mod, set()).add(ci.component)

    import_lines = []
    for mod in sorted(module_imports):
        names = ", ".join(sorted(module_imports[mod]))
        import_lines.append(f"from {mod} import {names}")

    # Build compile() body
    body_parts = []
    for ci in request.components:
        items = [(k, v) for k, v in ci.values.items() if v is not None]
        arg_lines = []
        for i, (k, v) in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            arg_lines.append(f"            {k}={_fmt(v)}{comma}")
        args_block = "\n".join(arg_lines)
        body_parts.append(
            f"        {ci.variable_name} = {ci.component}(\n"
            f"{args_block}\n"
            f"        )\n"
            f"        context.configuration.add({ci.variable_name})"
        )

    if body_parts:
        body = "\n\n".join(body_parts)
    else:
        body = "        pass"

    # Instantiation and filter
    inst_var = _to_snake_case(request.class_name)
    filter_block = f"\n{inst_var} = {request.class_name}()\n"
    if request.filter:
        filter_block += (
            f'{inst_var}.filters = FilterAttribute("{request.filter.attribute}")'
            f'.{request.filter.operator}("{request.filter.value}")\n'
        )

    code = (
        "\n".join(import_lines)
        + "\n\n\n"
        + f"class {request.class_name}(ConfigMap):\n"
        + f"    def compile(self, context):\n"
        + body
        + "\n\n"
        + filter_block
    )

    return GenerateResponse(code=code)


# ── Reconcile (diff → code) ───────────────────────────────────────


def _build_model_to_component_map() -> Dict[type, type]:
    """Reverse mapping: Pydantic model_cls → ConfigComponent class.
    Last-wins so that L3Vrf is preferred over NetworkInstance."""
    mapping = {}
    for cls in Configuration.COMPONENT_MAPPING:
        if not (isinstance(cls, type) and issubclass(cls, ConfigComponent)):
            continue
        model = getattr(cls, "model_cls", None)
        if model is not None:
            mapping[model] = cls
    return mapping


_model_to_component: Optional[Dict[type, type]] = None


def _get_model_to_component():
    global _model_to_component
    if _model_to_component is None:
        _model_to_component = _build_model_to_component_map()
    return _model_to_component


PYTHON_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield",
}


def _is_attribute_value_dict(v) -> bool:
    """Check if a dict looks like a serialised AttributeValue: {"value": ..., "metadata": ...}."""
    if not isinstance(v, dict):
        return False
    keys = set(v.keys())
    return "value" in keys and keys <= {"value", "metadata"}


def _unwrap_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unwrap a model_dump dict: extract .value from AttributeValue entries,
    skip None values, internal fields, and nested containers.
    """
    result = {}
    for k, v in d.items():
        if k in SKIP_FIELDS:
            continue
        if v is None:
            continue
        if _is_attribute_value_dict(v):
            raw = v.get("value")
            if raw is not None:
                result[k] = raw
        elif isinstance(v, AttributeValue):
            if v.value is not None:
                result[k] = v.value
        elif isinstance(v, dict):
            # Skip nested containers (vlans={}, interfaces={}, protocols={...})
            continue
        elif isinstance(v, list):
            if v:  # Only include non-empty lists
                result[k] = v
        else:
            result[k] = v
    return result


def _make_instance(comp_name, values, display, counter) -> ComponentInstance:
    """Build a ComponentInstance with a safe variable name."""
    var_name = re.sub(r"[^a-zA-Z0-9_]", "_", str(display)).lower().strip("_")
    if not var_name or not var_name[0].isalpha():
        var_name = f"{_to_snake_case(comp_name)}_{counter[0]}"
    if var_name in PYTHON_KEYWORDS:
        var_name = f"{var_name}_vrf"
    counter[0] += 1
    return ComponentInstance(
        component=comp_name,
        variable_name=var_name,
        values=values,
    )


def _changes_to_component_instances(
    changes, model_to_comp, counter
) -> List[ComponentInstance]:
    """Convert a list of ComponentChange into ComponentInstance specs."""
    instances = []
    for change in changes:
        comp_cls = model_to_comp.get(change.component_type)
        if comp_cls is None:
            continue

        comp_name = comp_cls.__name__

        # Use before_dict for removed, after_dict for changed
        raw = change.before_dict if change.op.value == "remove" else change.after_dict
        if raw is None:
            continue

        values = _unwrap_dict(raw)
        if not values:
            continue

        display = values.get("name", change.component_name)
        instances.append(_make_instance(comp_name, values, display, counter))

    return instances


# ── Full config → component instances ────────────────────────────


def _build_type_discriminator_map() -> Dict[str, str]:
    """Map component type discriminator value → ConfigComponent class name.
    E.g. 'ethernetCsmacd' → 'FrontpanelPort', 'softwareLoopback' → 'Loopback'."""
    mapping = {}
    for cls in Configuration.COMPONENT_MAPPING:
        if isinstance(cls, type) and issubclass(cls, ConfigComponent):
            comp_type = getattr(cls, "type", None)
            if comp_type:
                mapping[comp_type] = cls.__name__
    return mapping


def _navigate_dict(d, parts):
    """Navigate a plain dict by dot-path parts."""
    for part in parts:
        if not isinstance(d, dict):
            return None
        d = d.get(part)
        if d is None:
            return None
    return d


def _is_single_attr_component(comp_cls) -> bool:
    """True for components whose model_cls has only a 'value' field (HostName, Contact, …)."""
    model = getattr(comp_cls, "model_cls", None)
    if model is None:
        return False
    fields = model.model_fields
    return len(fields) == 1 and "value" in fields


def _is_container_component(comp_cls) -> bool:
    """True if the component's model_cls is a ContainerEntry (keyed in a dict)."""
    from acex_devkit.models.container_entry import ContainerEntry
    model = getattr(comp_cls, "model_cls", None)
    if model is None:
        return False
    return isinstance(model, type) and issubclass(model, ContainerEntry)


def _flatten_config_to_instances(config, model_to_comp) -> List[ComponentInstance]:
    """
    Walk a ComposedConfiguration (via model_dump dict) using COMPONENT_MAPPING
    paths to extract all non-empty components as ComponentInstance specs.

    Classification uses the component class itself:
    - Single-attr (HostName, Contact, …) → extract value from AttributeValue dict
    - Container (ContainerEntry subclass) → iterate dict entries, use type discriminator
    - Singleton model (SshServer, aaaGlobal, …) → unwrap fields directly
    """
    from string import Template

    if hasattr(config, "model_dump"):
        config_dict = config.model_dump()
    elif isinstance(config, dict):
        config_dict = config
    else:
        return []

    type_map = _build_type_discriminator_map()
    counter = [0]
    instances = []
    processed_paths = set()

    for comp_cls, mapped_path in Configuration.COMPONENT_MAPPING.items():
        if not (isinstance(comp_cls, type) and issubclass(comp_cls, ConfigComponent)):
            continue

        comp_name = comp_cls.__name__
        single_attr = _is_single_attr_component(comp_cls)
        container = _is_container_component(comp_cls)

        if isinstance(mapped_path, Template):
            _walk_template_dict(
                config_dict, mapped_path.template, comp_name,
                single_attr, container, type_map, counter, instances,
            )
        else:
            if mapped_path in processed_paths:
                continue
            processed_paths.add(mapped_path)

            obj = _navigate_dict(config_dict, mapped_path.split("."))
            if obj is None:
                continue

            _extract_from_dict(
                obj, comp_name, single_attr, container, type_map, counter, instances,
            )

    return instances


def _extract_from_dict(obj, comp_name, single_attr, container, type_map, counter, instances):
    """Extract ComponentInstance(s) from a dict found at a COMPONENT_MAPPING path."""

    if single_attr:
        # Singleton AttributeValue — e.g. {"value": "HQ-core-01"}
        if _is_attribute_value_dict(obj):
            raw = obj.get("value")
            if raw is not None:
                instances.append(_make_instance(
                    comp_name, {"value": raw},
                    _to_snake_case(comp_name), counter,
                ))
        return

    if container:
        # Dict of keyed entries — e.g. interfaces, ntp servers
        if not isinstance(obj, dict):
            return
        for key, item in obj.items():
            if not isinstance(item, dict):
                continue
            # Use type discriminator to resolve correct component
            resolved = comp_name
            item_type = item.get("type")
            if isinstance(item_type, dict):
                item_type = item_type.get("value")
            if item_type and item_type in type_map:
                resolved = type_map[item_type]

            values = _unwrap_dict(item)
            if values:
                display = values.get("name", key)
                instances.append(_make_instance(resolved, values, display, counter))
        return

    # Singleton model — e.g. SshServer, LoggingConfig
    if isinstance(obj, dict):
        values = _unwrap_dict(obj)
        if values:
            instances.append(_make_instance(
                comp_name, values,
                _to_snake_case(comp_name), counter,
            ))


def _walk_template_dict(config_dict, template_str, comp_name, single_attr, container, type_map, counter, results):
    """Walk a template path on a plain dict, expanding ${var} as wildcards."""
    segments = []
    for part in template_str.split("."):
        segments.append(None if "${" in part else part)

    def recurse(obj, idx):
        if obj is None:
            return
        if idx >= len(segments):
            _extract_from_dict(obj, comp_name, single_attr, container, type_map, counter, results)
            return
        seg = segments[idx]
        if seg is None:
            if isinstance(obj, dict):
                for child in obj.values():
                    if isinstance(child, dict):
                        recurse(child, idx + 1)
        else:
            if isinstance(obj, dict):
                recurse(obj.get(seg), idx + 1)

    recurse(config_dict, 0)


# ── Router ────────────────────────────────────────────────────────


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/config_components")
    tags = ["Config Maps"]

    # Reconcile needs access to the diff engine
    from acex.config_diff import DiffLogicalNode
    differ = DiffLogicalNode(
        automation_engine.inventory,
        automation_engine.device_config_manager,
    )

    async def reconcile(node_instance_id: str, options: Optional[ReconcileOptions] = None):
        """
        Generate a ConfigMap from observed device config.

        Two modes:
        - "diff":  Only components that are missing from or differ in desired
                   config (uses structural diff).
        - "full":  All components from the observed parsed config, regardless
                   of desired state. Useful for bootstrapping desired state
                   from a running device.
        """
        if options is None:
            options = ReconcileOptions()

        model_to_comp = _get_model_to_component()
        component_instances = []

        if options.mode == "full":
            stored = await automation_engine.device_config_manager.get_latest_config(
                node_instance_id, "parsed"
            )
            if stored is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No observed parsed config found for {node_instance_id}",
                )
            # stored is a StoredDeviceConfig — .content holds the ComposedConfiguration
            component_instances = _flatten_config_to_instances(stored.content, model_to_comp)
        else:
            diff = await differ.diff(node_instance_id)
            counter = [0]
            if options.include_removed:
                component_instances.extend(
                    _changes_to_component_instances(diff.removed, model_to_comp, counter)
                )
            if options.include_changed:
                component_instances.extend(
                    _changes_to_component_instances(diff.changed, model_to_comp, counter)
                )

        if not component_instances:
            return GenerateResponse(
                code="# No components to reconcile — desired config matches observed."
            )

        # Generate one ConfigMap per component
        code_blocks = []
        seen_names = set()
        for ci in component_instances:
            # Auto-generate a unique class name from component type + variable name
            base = f"Configure{ci.component}_{ci.variable_name}"
            # Clean to valid Python identifier
            class_name = re.sub(r"[^a-zA-Z0-9]", "_", base).strip("_")
            # Deduplicate
            unique = class_name
            n = 2
            while unique in seen_names:
                unique = f"{class_name}_{n}"
                n += 1
            seen_names.add(unique)

            request = GenerateRequest(
                class_name=unique,
                filter=options.filter,
                components=[ci],
            )
            result = generate_configmap(request)
            code_blocks.append(result.code)

        return GenerateResponse(code="\n\n".join(code_blocks))

    router.add_api_route(
        "/",
        list_components,
        methods=["GET"],
        response_model=ComponentCatalog,
        tags=tags,
    )
    router.add_api_route(
        "/generate",
        generate_configmap,
        methods=["POST"],
        response_model=GenerateResponse,
        tags=tags,
    )
    router.add_api_route(
        "/reconcile/{node_instance_id}",
        reconcile,
        methods=["POST"],
        response_model=GenerateResponse,
        tags=tags,
    )

    return router
