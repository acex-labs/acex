"""
Per-type rendering of `Augment`-class components into Junos CLI lines.

Mirrors the Cisco driver's dispatch pattern. Augments unknown to this
driver (no renderer registered for that type) are silently skipped.

Junos-set commands are flat (no indented blocks like Cisco), so renderer
functions emit fully-formed `set ...` lines. They receive `target_path`
so they can extract context (e.g. the SNMP community name) from it.

To add a new Juniper augment type:
  1. Define the augment component + payload model in the backend
  2. Register a renderer here under its `type` key
"""
from collections import defaultdict
from typing import Callable, Dict, List


def _render_snmp_community_clients(aug: dict, target_path: str) -> List[str]:
    """`set snmp community <name> clients <prefix>` — one line per prefix."""
    community_name = target_path.rsplit(".", 1)[-1]
    clients = (aug.get("clients") or {}).get("value") or []
    return [
        f"set snmp community {community_name} clients {prefix}"
        for prefix in clients
    ]


AUGMENT_RENDERERS: Dict[str, Callable[[dict, str], List[str]]] = {
    "juniper.snmp_community_clients": _render_snmp_community_clients,
}


def resolve_augment_lines(configuration: dict) -> Dict[str, List[str]]:
    """
    Walk every targetable tree node, collect its `augments` dict, dispatch each
    augment to its renderer, and return a {target_path: [cli_line, ...]} dict
    for use in Jinja.

    Augments unknown to this driver (no renderer registered for that type)
    are silently skipped — that's the point of augment-on-target dispatch.
    """
    by_target: Dict[str, List[str]] = defaultdict(list)

    def _collect(target_path: str, augments: dict):
        for aug_type, aug in (augments or {}).items():
            renderer = AUGMENT_RENDERERS.get(aug_type)
            if renderer is None:
                continue
            by_target[target_path].extend(renderer(aug, target_path))

    for name, intf in (configuration.get("interfaces") or {}).items():
        _collect(f"interfaces.{name}", intf.get("augments"))

    for name, tmpl in (configuration.get("interface_templates") or {}).items():
        _collect(f"interface_templates.{name}", tmpl.get("augments"))

    # SNMP communities — Junos has per-community augments (e.g. clients list)
    for name, com in (((configuration.get("system") or {}).get("snmp") or {}).get("communities") or {}).items():
        _collect(f"system.snmp.communities.{name}", com.get("augments"))

    # Singletons under system.* — extend here as more Augmentable targets land.
    vtp_cfg = ((configuration.get("system") or {}).get("vtp") or {}).get("config")
    if vtp_cfg:
        _collect("system.vtp.config", vtp_cfg.get("augments"))

    return dict(by_target)
