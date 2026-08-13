"""Observability namespace — telemetry agents and Grafana renders."""

from __future__ import annotations

from acex_client.http import RestClient
from acex_client.resources.observability.agents import ObservabilityAgents
from acex_client.resources.observability.grafana import Grafana


class ObservabilityNamespace:
    def __init__(self, rest: RestClient):
        self.agents = ObservabilityAgents(rest)
        self.grafana = Grafana(rest)
