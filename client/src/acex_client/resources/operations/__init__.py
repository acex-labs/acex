"""Operations namespace — compliance checks, config change history, LLDP neighbors."""

from __future__ import annotations

from acex_client.http import RestClient
from acex_client.resources.operations.compliance import Compliance
from acex_client.resources.operations.config_history import ConfigHistory
from acex_client.resources.operations.lldp import Lldp


class OperationsNamespace:
    def __init__(self, rest: RestClient):
        self.compliance = Compliance(rest)
        self.config_history = ConfigHistory(rest)
        self.lldp = Lldp(rest)
