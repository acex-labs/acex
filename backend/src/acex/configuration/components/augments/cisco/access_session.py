"""
Cisco Access-Session augment.

Models ``access-session attributes filter-list``,
``access-session authentication/accounting attributes filter-spec`` commands.
Renders to::

    access-session attributes filter-list list Def_Acct_List
     cdp
     lldp
     dhcp
     http
    !
    access-session authentication attributes filter-spec include list Def_Auth_List
    access-session accounting attributes filter-spec include list Def_Acct_List

The entire access-session configuration block is held in a single augment
instance that targets ``ServicesConfig``.
"""

from typing import Dict, Literal, Optional

from pydantic import BaseModel

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.services import ServicesConfig
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes

# -- nested payload models -------------------------------------------------


class AccessSessionFilterItem(BaseModel):
    """Single protocol/attribute entry within an access-session filter list."""

    name: AttributeValue[str]


class AccessSessionFilterList(BaseModel):
    """``access-session attributes filter-list list {name}``."""

    name: AttributeValue[str]
    items: Dict[str, AccessSessionFilterItem] = {}


class AccessSessionFilterSpec(BaseModel):
    """``access-session {context} attributes filter-spec {action} list {name}``."""

    action: AttributeValue[str]  # include | exclude
    filter_list: AttributeValue[str]  # name of the referenced filter-list


# -- augment attribute model -----------------------------------------------


class CiscoAccessSessionAttributes(AugmentAttributes):
    """Full access-session configuration block."""

    type: Literal["cisco.access_session"] = "cisco.access_session"
    attribute_filter_lists: Dict[str, AccessSessionFilterList] = {}
    authentication_filter_spec: Optional[AccessSessionFilterSpec] = None
    accounting_filter_spec: Optional[AccessSessionFilterSpec] = None


# -- augment component -----------------------------------------------------


class CiscoAccessSession(Augment):
    """
    Cisco access-session augment, targets ``ServicesConfig``.

    Integrator kwargs (transformed by ``pre_init``):

    * **attribute_filter_lists** -- ``dict[str, dict]`` keyed by list name::

          {"Def_Acct_List": {"items": ["cdp", "lldp", "dhcp", "http"]}}

    * **authentication_filter_spec** -- ``dict``::

          {"action": "include", "filter_list": "Def_Auth_List"}

    * **accounting_filter_spec** -- ``dict``::

          {"action": "include", "filter_list": "Def_Acct_List"}
    """

    type = "cisco.access_session"
    model_cls = CiscoAccessSessionAttributes
    default_vendor = "cisco"
    valid_targets = (ServicesConfig,)

    def pre_init(self):
        # Expand shorthand attribute_filter_lists: items list[str] -> Dict
        raw_lists = self.kwargs.get("attribute_filter_lists")
        if isinstance(raw_lists, dict):
            expanded = {}
            for list_name, cfg in raw_lists.items():
                items_raw = cfg.get("items", [])
                items = (
                    {item: {"name": item} for item in items_raw}
                    if isinstance(items_raw, list)
                    else items_raw
                )
                expanded[list_name] = {
                    "name": list_name,
                    "items": items,
                }
            self.kwargs["attribute_filter_lists"] = expanded

        # Let Augment.pre_init handle target extraction
        super().pre_init()
