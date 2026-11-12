"""Policies namespace — what the environment is held to, one resource per policy type."""

from __future__ import annotations

from acex_client.http import RestClient
from acex_client.resources.policies.software import SoftwarePolicies


class PoliciesNamespace:
    def __init__(self, rest: RestClient):
        self.software = SoftwarePolicies(rest)
