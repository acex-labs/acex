"""
Cisco IOS / IOS-XE access session attachment.

Attaches globally-defined access-session filter lists and filter specs by name
"""
from typing import Literal

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.services import Services

from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes

from pydantic import BaseModel

class FilterListOptionsAttributes(AugmentAttributes):
    """
    access-session attributes filter-list list {list_name}
      cdp
      lldp << this is the data you set in this model
      -- etc. --
    """
    type: Literal["cisco.access_session_filter_list_options"] = "cisco.access_session_filter_list_options"
    name: AttributeValue[str]
    #protocol: AttributeValue[str]  # e.g. "cdp"
    items: list[AttributeValue[str]] = []
 
class CiscoAccessSessionFilterListOptions(Augment):
    type = "cisco.access_session_filter_list_options"
    model_cls = FilterListOptionsAttributes
    valid_targets = (Services,)
    default_vendor = "cisco"
    
#class CiscoAccessSessionFilterSpecAttributes(AugmentAttributes):
#    """
#    access-session attributes filter-spec {protocol} {action} list {list_name}
#      cdp
#      lldp << this is the data you set in this model
#      -- etc. --
#    """
#    type: Literal["cisco.access_session"] = "cisco.access_session"
#    protocol: AttributeValue[str]  # e.g. "cdp"
#    action: AttributeValue[str]  # e.g. "include"
#    filter_list: AttributeValue[str]  # name of the referenced filter-list
    

class FilterList(AugmentAttributes):
    "Attaches named access-session filter lists and filter specs to Services."
    type: Literal["cisco.access_session_filter_list"] = "cisco.access_session_filter_list"
    list_attributes: dict[str, FilterListOptionsAttributes] = {}
    
class CiscoAccessSessionFilterList(Augment):
    type = "cisco.access_session_filter_list"
    model_cls = FilterList
    valid_targets = (Services,)
    default_vendor = "cisco"