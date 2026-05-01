"""
Juniper SNMP community client restriction.

Restricts an SNMP community to a list of client source networks/hosts.
Juniper-specific feature (corresponds to `set snmp community <name>
clients <prefix>` in Junos). Other vendors model client restrictions
through ACL references (`ipv4_acl` etc. on SnmpCommunity).
"""
from typing import List, Literal

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.snmp import SnmpCommunity
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes


class JuniperSnmpCommunityClientsAttributes(AugmentAttributes):
    "Restricts an SNMP community to a list of client networks (Juniper-specific)."
    type: Literal["juniper.snmp_community_clients"] = "juniper.snmp_community_clients"
    clients: AttributeValue[List[str]]


class JuniperSnmpCommunityClients(Augment):
    type = "juniper.snmp_community_clients"
    model_cls = JuniperSnmpCommunityClientsAttributes
    valid_targets = (SnmpCommunity,)
    default_vendor = "juniper"
