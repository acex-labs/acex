"""Cisco IOS / IOS-XE access session attachment."""

from typing import Dict, List, Literal, Optional

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.services import Services

from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes, ReferenceTo

from pydantic import BaseModel, Field



class CiscoAccessSessionFilterListAttributes(AugmentAttributes):
    type: Literal["cisco_access_session_filter_list"] = "cisco_access_session_filter_list"


class CiscoAccessSessionFilterList(Augment):
    "Named access-session filter-list payload."
    type: Literal["cisco_access_session_filter_list"] = "cisco_access_session_filter_list"
    model_cls = CiscoAccessSessionFilterListAttributes
    valid_targets = (Services, )
    default_vendor = "cisco"


class CiscoAccessSessionAttributes(AugmentAttributes):
    type: Literal["cisco_access_session"] = "cisco_access_session"
    filter_lists: Dict[str, ReferenceTo] = Field(default_factory=dict)


class CiscoAccessSessionAuthentication(Augment):
    type = "cisco_access_session_authentication"
    model_cls = CiscoAccessSessionAttributes
    valid_targets = (Services,)
    default_vendor = "cisco"








# class AccessSessionAuthenticationSpec(AccessSessionFilterSpec):
#     pass


# class AccessSessionAuthorizationSpec(AccessSessionFilterSpec):
#     pass


# class AccessSessionAccountingSpec(AccessSessionFilterSpec):
#     pass


# class CiscoAccessSessionAttributes(AugmentAttributes):
#     type: Literal["cisco_access_session"] = "cisco_access_session"
#     filter_lists: Dict[str, CiscoAccessSessionFilterList] = Field(default_factory=dict)
#     authentication: Optional[AccessSessionAuthenticationSpec] = None
#     authorization: Optional[AccessSessionAuthorizationSpec] = None
#     accounting: Optional[AccessSessionAccountingSpec] = None


# class CiscoAccessSession(Augment):
#     type = "cisco_access_session"
#     model_cls = CiscoAccessSessionAttributes
#     valid_targets = (Services,)
#     default_vendor = "cisco"

