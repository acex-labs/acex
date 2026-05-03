"""
Telegraf TOML rendering driven by TelemetryComponents.

Free functions (`render_agent_section`, `render_inputs`) compose into
`TelemetryAgentManager._render_telegraf_config`, so the per-agent endpoint
and any future global rendering share the same input source.
"""
from typing import Any, Iterable

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


def _render_input_block(plugin: str, config: dict[str, Any], tags: dict[str, str]) -> list[str]:
    lines = _render_kv_block(f"[[inputs.{plugin}]]", config)
    if tags:
        lines.append(f"  [inputs.{plugin}.tags]")
        for k, v in tags.items():
            lines.append(f"    {k} = {_format_value(v)}")
    lines.append("")
    return lines


def render_agent_section(
    interval: str = "60s",
    flush_interval: str = "10s",
    hostname: str = "",
) -> str:
    return "\n".join([
        "[agent]",
        f'  hostname = "{hostname}"',
        f'  interval = "{interval}"',
        f'  flush_interval = "{flush_interval}"',
        "",
    ])


def render_inputs(components: Iterable[TelemetryComponent]) -> str:
    """Render only the [[inputs.X]] blocks for the given components.

    Components whose `telegraf_input()` returns None are skipped.
    """
    lines: list[str] = []
    for c in components:
        block = c.telegraf_input()
        if block is None:
            continue
        lines.extend(_render_input_block(
            plugin=block["plugin"],
            config=block.get("config", {}),
            tags=block.get("tags", {}),
        ))
    return "\n".join(lines)
