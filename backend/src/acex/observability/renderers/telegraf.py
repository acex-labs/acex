"""
Telegraf TOML rendering driven by TelemetryComponents.

Free functions (`render_agent_section`, `render_inputs`) compose into
`TelemetryAgentManager._render_telegraf_config`, so the per-agent endpoint
and any future global rendering share the same input source.
"""

from collections.abc import Iterable
from typing import Any

from acex.observability.components.base import TelemetryComponent


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    raise TypeError(f"Unsupported telegraf TOML value: {type(value).__name__}")


def _render_kv_block(table: str, items: dict[str, Any], indent: str = "  ") -> list[str]:
    lines = [table]
    for key, value in items.items():
        lines.append(f"{indent}{key} = {_format_value(value)}")
    return lines


def _render_input_block(
    plugin: str,
    config: dict[str, Any],
    tags: dict[str, str],
    subtables: list[dict] | None = None,
) -> list[str]:
    lines = _render_kv_block(f"[[inputs.{plugin}]]", config)
    if tags:
        lines.append(f"  [inputs.{plugin}.tags]")
        for k, v in tags.items():
            lines.append(f"    {k} = {_format_value(v)}")
    for sub in subtables or []:
        lines.append("")
        lines.extend(_render_kv_block(f"  [[inputs.{plugin}.{sub['name']}]]", sub["data"], indent="    "))
    lines.append("")
    return lines


def render_agent_section(
    interval: str = "60s",
    flush_interval: str = "10s",
    hostname: str = "",
) -> str:
    return "\n".join(
        [
            "[agent]",
            f'  hostname = "{hostname}"',
            f'  interval = "{interval}"',
            f'  flush_interval = "{flush_interval}"',
            "",
        ]
    )


def render_inputs(components: Iterable[TelemetryComponent]) -> str:
    """Render only the [[inputs.X]] blocks for the given components.

    Components whose `telegraf_input()` returns None are skipped.
    """
    lines: list[str] = []
    for c in components:
        block = c.telegraf_input()
        if block is None:
            continue
        lines.extend(
            _render_input_block(
                plugin=block["plugin"],
                config=block.get("config", {}),
                tags=block.get("tags", {}),
                subtables=block.get("subtables"),
            )
        )
    return "\n".join(lines)


def render_snmp_trap_input(
    service_address: str = "udp://:162",
    version: str = "2c",
    community: str | None = None,
    sec_name: str | None = None,
    auth_protocol: str | None = None,
    auth_password: str | None = None,
    sec_level: str | None = None,
    priv_protocol: str | None = None,
    priv_password: str | None = None,
) -> str:
    """Render an `[[inputs.snmp_trap]]` block.

    `version` is one of "2c", "3", or "both". Two `[[inputs.snmp_trap]]`
    blocks cannot share a UDP port, so "both" is rendered as a single
    v3 block — gosnmp does not filter by configured version when
    receiving, so v2c traps are still accepted (without community
    validation). v3 authentication fields are only relevant when
    version includes "3".
    """
    if version == "both":
        version = "3"

    cfg: dict[str, Any] = {"service_address": service_address, "version": version}
    if version == "2c":
        if community:
            cfg["community"] = community
    else:
        if sec_name:
            cfg["sec_name"] = sec_name
        if auth_protocol:
            cfg["auth_protocol"] = auth_protocol
        if auth_password:
            cfg["auth_password"] = auth_password
        if sec_level:
            cfg["sec_level"] = sec_level
        if priv_protocol:
            cfg["priv_protocol"] = priv_protocol
        if priv_password:
            cfg["priv_password"] = priv_password

    lines = _render_kv_block("[[inputs.snmp_trap]]", cfg)
    lines.append("")
    return "\n".join(lines)


def render_syslog_input(
    server: str = "udp://:514",
) -> str:
    """Render an `[[inputs.syslog]]` block (RFC5424 over UDP)."""
    lines = _render_kv_block(
        "[[inputs.syslog]]",
        {"server": server, "syslog_standard": "RFC5424"},
    )
    lines.append("")
    return "\n".join(lines)
