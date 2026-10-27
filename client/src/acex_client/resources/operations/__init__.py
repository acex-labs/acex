"""Operations namespace — compliance checks, config change history, LLDP neighbors, runs on nodes, workflows."""

from __future__ import annotations

from acex_client.http import RestClient
from acex_client.resources.operations.compliance import Compliance
from acex_client.resources.operations.config_history import ConfigHistory
from acex_client.resources.operations.lldp import Lldp
from acex_client.resources.operations.runs import Actions, Execute, Runs
from acex_client.resources.operations.workflows import Workflows


class OperationsNamespace:
    def __init__(self, rest: RestClient):
        self.compliance = Compliance(rest)
        self.config_history = ConfigHistory(rest)
        self.execute = Execute(rest)
        self.actions = Actions(rest)
        self.runs = Runs(rest)
        self.lldp = Lldp(rest)
        self.workflows = Workflows(rest)
