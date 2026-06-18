"""Cisco IOS / IOS-XE AAA augments."""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.aaa import aaaAuthenticationConfig, aaaAccountingConfig, aaaAuthorizationConfig
from acex_devkit.models import AttributeValue
from acex_devkit.models.augment import AugmentAttributes
from acex_devkit.models.reference import ReferenceTo, Reference

class CiscoAuthMethod(BaseModel):
    method: str #Literal["group", "local", "line", "enable", "none"]

# Gör PreAuth till samma?
class CiscoPreAuthentication(AugmentAttributes):
    type: Literal["cisco_pre_authentication"] = "cisco_pre_authentication"
    name: Optional[AttributeValue[str]] = None # default, CONSOLE, etc.
    auth_type: Optional[AttributeValue[str]] = None #= Literal['login', 'enable', 'dot1x']
    group_type: Optional[AttributeValue[str]] = None #= Literal['tacacs+', 'radius']
    #group_name: Optional[Reference]#Optional[AttributeValue[str]] = None # srv-grp, either a name or radius/tacacs+
    # behöver vara fler alt. Lista?
    # eller methods och sen göra dict str?
    #method: str = Literal["local", "line", "enable", "none"] # "local", "line", "enable", "none" ; literal?
    methods: Optional[AttributeValue[List[str]]] = None
    #methods: Optional[Dict[str, AuthMethod]]

class CiscoPreAuthorization(AugmentAttributes):
    type: Literal["cisco_pre_authorization"] = "cisco_pre_authorization"
    name: Optional[AttributeValue[str]] = None # default, CONSOLE, etc.
    author_type: Optional[AttributeValue[str]] = None #= Literal['exec', 'commands', 'console', 'config-commands', 'interactive-commands']
    group_type: Optional[AttributeValue[str]] = None #= Literal['tacacs+', 'radius']
    #group_name: Optional[AttributeValue[str]] = None # srv-grp, either a name or radius/tacacs+
    methods: Optional[AttributeValue[List[str]]] = None
    #method: str = Literal["local", "line", "enable", "none"] # "local", "line", "enable", "none" ; literal?
    if_authenticated: Optional[AttributeValue[bool]] = None
    privilege_level: Optional[int] = None # Only for commands
    
class CiscoPreAccounting(AugmentAttributes):
    type: Literal["cisco_pre_accounting"] = "cisco_pre_accounting"
    name: Optional[AttributeValue[str]] = None # default, CONSOLE, etc.
    account_type: Optional[AttributeValue[str]] = None #= Literal['exec', 'commands', 'identity']
    group_type: Optional[AttributeValue[str]] = None #= Literal['tacacs+', 'radius']
    #group_name: Optional[AttributeValue[str]] = None # srv-grp, either a name or radius/tacacs+
    methods: Optional[AttributeValue[List[str]]] = None
    #method: str = Literal["start-stop", "stop-only", "none", "wait-start"] # "start-stop", "stop-only", "none", "wait-start" ; literal?
    privilege_level: Optional[int] = None # Only for commands
    
class CiscoAaaAuthentication(Augment):
    """
    Authentication method list for login or enable.
    Ex. command:
    aaa authentication login default group ISE-TACACS+ local line enable.
    """
    type = "cisco_aaa_authentication"
    model_cls = CiscoPreAuthentication
    valid_targets = (aaaAuthenticationConfig,)
    default_vendor = "cisco"
    singleton = False
    
    def pre_init(self):
        #group_name = self.kwargs.get("group_name")
        #group_type = self.kwargs.get("group_type")
        if self.kwargs.get('group_name') is not None and self.kwargs.get('group_type') is not None:
            if self.kwargs.get('group_type') == "tacacs+":
                group = self.kwargs.pop("group_name")
                self.kwargs["group"] = ReferenceTo(pointer=f"system.aaa.server_groups.{group.name}.tacacs")
            if self.kwargs.get('group_type') == "radius":
                group = self.kwargs.pop("group_name")
                self.kwargs["group"] = ReferenceTo(pointer=f"system.aaa.server_groups.{group.name}.radius")
        super().pre_init()

class CiscoAaaAuthorization(Augment):
    """
    Authorization method list for exec or commands.
    Ex. command:
    aaa authorization exec default group ISE-TACACS+ local line enable.
    """
    type = "cisco_aaa_authorization"
    model_cls = CiscoPreAuthorization
    valid_targets = (aaaAuthorizationConfig,)
    default_vendor = "cisco"
    singleton = False

    def pre_init(self):
        #group_name = self.kwargs.get("group_name")
        #group_type = self.kwargs.get("group_type")
        if self.kwargs.get('group_name') is not None and self.kwargs.get('group_type') is not None:
            if self.kwargs.get('group_type') == "tacacs+":
                group = self.kwargs.pop("group_name")
                self.kwargs["group"] = ReferenceTo(pointer=f"system.aaa.server_groups.{group.name}.tacacs")
            if self.kwargs.get('group_type') == "radius":
                group = self.kwargs.pop("group_name")
                self.kwargs["group"] = ReferenceTo(pointer=f"system.aaa.server_groups.{group.name}.radius")
        super().pre_init()
    
class CiscoAaaAccounting(Augment):
    """
    Accounting method list for login or enable.
    Ex. command:
    aaa accounting login default group ISE-TACACS+ local line enable.
    """
    type = "cisco_aaa_accounting"
    model_cls = CiscoPreAccounting
    valid_targets = (aaaAccountingConfig,)
    default_vendor = "cisco"
    singleton = False

    def pre_init(self):
        #group_name = self.kwargs.get("group_name")
        #group_type = self.kwargs.get("group_type")
        if self.kwargs.get('group_name') is not None and self.kwargs.get('group_type') is not None:
            if self.kwargs.get('group_type') == "tacacs+":
                group = self.kwargs.pop("group_name")
                self.kwargs["group"] = ReferenceTo(pointer=f"system.aaa.server_groups.{group.name}.tacacs")
            if self.kwargs.get('group_type') == "radius":
                group = self.kwargs.pop("group_name")
                self.kwargs["group"] = ReferenceTo(pointer=f"system.aaa.server_groups.{group.name}.radius")
        super().pre_init()