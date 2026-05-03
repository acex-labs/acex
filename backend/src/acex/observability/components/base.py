from typing import ClassVar, Optional

from acex.observability.capability import TelemetryCapability


class TelemetryComponent:
    """
    Intent-driven observability declaration.

    A TelemetryComponent represents one measurable aspect of a target
    (a node, a BGP neighbor, an interface). It binds together three views
    of the same metric so they cannot drift apart:

      - what telegraf needs to do to collect it (`telegraf_input`)
      - the resulting InfluxDB measurement and tag schema (`measurement`, `tags`)
      - the identity used in Grafana queries (`tags`)
      - which TelemetryAgent capability gates collection (`capability`)
      - which node-instance this component belongs to (`target_node`)

    Concrete subclasses set `kind`, `measurement`, and `capability` as
    class vars and implement `target_id`, `tags`, `target_node`, and
    `telegraf_input`.

    Panels are not produced per component — dashboards are written explicitly
    and pull components from the registry to know what to query.
    """

    kind: ClassVar[str] = ""
    measurement: ClassVar[str] = ""
    capability: ClassVar[Optional[TelemetryCapability]] = None

    def target_id(self) -> str:
        """Stable identifier for the target this component observes (e.g. "node:5")."""
        raise NotImplementedError

    def target_node(self) -> Optional[int]:
        """Node-instance id this component belongs to, or None if cross-node."""
        return None

    def tags(self) -> dict[str, str]:
        """Tag set this component contributes to its measurement in InfluxDB."""
        return {}

    def telegraf_input(self) -> Optional[dict]:
        """
        Telegraf input plugin block for this component, or None if this
        component piggybacks on something else.

        Shape:
            {
                "plugin": "ping",
                "config": {"urls": ["1.1.1.1"], "count": 3, ...},
                "tags": {"node": "router1", "site": "HQ"},
            }
        """
        return None
