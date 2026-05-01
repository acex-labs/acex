"""
Per-type rendering of `Augment`-class components into Cisco IOS CLI lines.

The driver-level pre_process walks every targetable node's `augments` slot,
dispatches each augment to its renderer based on the augment `type`
discriminator, and groups the resulting lines by target path. Jinja then
just iterates the lines for a given target — no type discrimination in the
template.

To add a new Cisco augment type:
  1. Define the augment component + payload model in the backend
  2. Register a renderer here under its `type` key
"""
from collections import defaultdict
from typing import Callable, Dict, List


def _render_device_tracking_policy(aug: dict) -> List[str]:
    return [f"device-tracking attach-policy {aug['policy_name']['value']}"]


def _render_service_policy(aug: dict) -> List[str]:
    lines = []
    if aug.get("input_policy"):
        lines.append(f"service-policy input {aug['input_policy']['value']}")
    if aug.get("output_policy"):
        lines.append(f"service-policy output {aug['output_policy']['value']}")
    return lines


def _render_vtp_primary_server(aug: dict) -> List[str]:
    enabled = (aug.get("enabled") or {}).get("value")
    if enabled:
        return ["vtp primary server"]
    return []


AUGMENT_RENDERERS: Dict[str, Callable[[dict], List[str]]] = {
    "cisco.device_tracking_policy": _render_device_tracking_policy,
    "cisco.service_policy": _render_service_policy,
    "cisco.vtp_primary_server": _render_vtp_primary_server,
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
            by_target[target_path].extend(renderer(aug))

    for name, intf in (configuration.get("interfaces") or {}).items():
        _collect(f"interfaces.{name}", intf.get("augments"))

    for name, tmpl in (configuration.get("interface_templates") or {}).items():
        _collect(f"interface_templates.{name}", tmpl.get("augments"))

    # Singletons under system.* — extend here as more Augmentable targets land.
    vtp_cfg = ((configuration.get("system") or {}).get("vtp") or {}).get("config")
    if vtp_cfg:
        _collect("system.vtp.config", vtp_cfg.get("augments"))

    return dict(by_target)
