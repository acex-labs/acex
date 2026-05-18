"""
Cisco IOS / IOS-XE access session attachment.

Attaches globally-defined access-session filter lists and filter specs by name
"""
from typing import Optional, Dict, List, Literal, ClassVar, Union, Any

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.services import Services

from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes

from pydantic import BaseModel

class FilterListOptionsAttribute(AugmentAttributes):
    """
    access-session attributes filter-list list {list_name}
      cdp
      lldp << this is the data you set in this model
      -- etc. --
    """
    type: Literal["cisco.access_session_filter_option"] = "cisco.access_session_filter_option"
    #name: AttributeValue[str]
    #protocol: AttributeValue[str]  # e.g. "cdp"
    item: AttributeValue[str] # e.g. "cdp", "lldp", "dhcp", "http" -- this is the data you set in this model
 
class CiscoAccessSessionFilterListOption(Augment):
    """
    access-session attributes filter-spec include list {list_name}
    """
    #type: Literal["cisco.access_session_filter_list_option"] = "cisco.access_session_filter_list_option"
    #name: AttributeValue[str]
    type = "cisco.access_session_filter_option"
    model_cls = FilterListOptionsAttribute
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
    #list_attributes: Dict[str, FilterListOptionsAttribute] = {}
    items: AttributeValue[List[str]] # e.g. ["cdp", "lldp", "dhcp", "http"] -- this is the data you set in this model
    
class CiscoAccessSessionFilterList(Augment):
    type = "cisco.access_session_filter_list"
    model_cls = FilterList
    valid_targets = (Services,)
    default_vendor = "cisco"
    

#########

# Authentication
"""
access-session attributes filter-list list Def_Auth_List
 vlan-id
!
access-session authentication attributes filter-spec include list Def_Auth_List
"""
#class 

# Authorization

# Accounting
"""
access-session attributes filter-list list Def_Acct_List
 cdp
 lldp
 dhcp
 http
!
access-session accounting attributes filter-spec include list Def_Acct_List
"""
