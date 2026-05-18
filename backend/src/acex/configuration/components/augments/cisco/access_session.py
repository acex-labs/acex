"""Cisco IOS / IOS-XE access session attachment."""

from typing import Dict, List, Literal, Optional

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.services import Services

from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes

from pydantic import BaseModel, Field


class AccessSessionFilterList(BaseModel):
    "Named access-session filter-list payload."

    items: AttributeValue[List[str]]


class AccessSessionFilterSpec(BaseModel):
    "Shared filter-spec payload for authentication, authorization, and accounting."

    action: AttributeValue[str]  # include / exclude
    filter_list: AttributeValue[str]


class AccessSessionAuthenticationSpec(AccessSessionFilterSpec):
    pass


class AccessSessionAuthorizationSpec(AccessSessionFilterSpec):
    pass


class AccessSessionAccountingSpec(AccessSessionFilterSpec):
    pass


class CiscoAccessSessionAttributes(AugmentAttributes):
    type: Literal["cisco.access_session"] = "cisco.access_session"
    filter_lists: Dict[str, AccessSessionFilterList] = Field(default_factory=dict)
    authentication: Optional[AccessSessionAuthenticationSpec] = None
    authorization: Optional[AccessSessionAuthorizationSpec] = None
    accounting: Optional[AccessSessionAccountingSpec] = None


class CiscoAccessSession(Augment):
    type = "cisco.access_session"
    model_cls = CiscoAccessSessionAttributes
    valid_targets = (Services,)
    default_vendor = "cisco"


#__all__ = [
#    "AccessSessionAccountingSpec",
#    "AccessSessionAuthenticationSpec",
#    "AccessSessionAuthorizationSpec",
#    "AccessSessionFilterList",
#    "CiscoAccessSession",
#    "CiscoAccessSessionAttributes",
#]
