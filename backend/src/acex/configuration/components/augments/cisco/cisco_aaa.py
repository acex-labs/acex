"""Cisco IOS / IOS-XE AAA augments."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.aaa import (
    aaaAuthenticationConfig,
    aaaAccountingConfig,
    aaaAuthorizationConfig,
    aaaServerGroup,
)
from acex.configuration.components.system.logging import Console, VtyLine
from acex_devkit.models import AttributeValue
from acex_devkit.models.augment import AugmentAttributes
from acex_devkit.models.reference import ReferenceTo, Reference


class CiscoAuthMethod(BaseModel):
    method: str  # Literal["group", "local", "line", "enable", "none"]


# Convert internal unique augment names into stable Cisco AAA list names.
# ACEX requires unique object names (often with numeric suffixes), but CLI
# method-list names should be shared across privilege levels (for example,
# CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST_2 -> CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST)
# and default_* variants should render as just "default".
def _derive_cli_list_name(name: Optional[str]) -> Optional[str]:
    if not isinstance(name, str) or not name:
        return name
    if name.startswith("default_"):
        return "default"
    if "_" in name:
        tail = name.rsplit("_", 1)[1]
        if tail.isdigit():
            return name.rsplit("_", 1)[0]
    return name

class CiscoAaaAuthenticationAttributes(AugmentAttributes):
    type: Literal["cisco_pre_authentication"] = "cisco_pre_authentication"
    name: Optional[AttributeValue[str]] = None  # default, CONSOLE, etc.
    cli_list_name: Optional[str] = (
        None  # if not provided, derived from name (e.g. CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST_2 -> CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST)
    )
    auth_type: Optional[AttributeValue[str]] = (
        None  # = Literal['login', 'enable', 'dot1x']
    )
    group_type: Optional[AttributeValue[str]] = None  # = Literal['tacacs+', 'radius']
    methods: Optional[AttributeValue[List[str]]] = (
        None  # list of method names, e.g. ["local", "line", "enable"] or ["group"] with group reference
    )

class CiscoAaaAuthorizationAttirbutes(AugmentAttributes):
    type: Literal["cisco_pre_authorization"] = "cisco_pre_authorization"
    name: Optional[AttributeValue[str]] = None  # default, CONSOLE, etc.
    cli_list_name: Optional[str] = (
        None  # if not provided, derived from name (e.g. CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST_2 -> CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST)
    )
    author_type: Optional[AttributeValue[str]] = (
        None  # = Literal['exec', 'commands', 'console', 'config-commands', 'interactive-commands']
    )
    group_type: Optional[AttributeValue[str]] = None  # = Literal['tacacs+', 'radius']
    methods: Optional[AttributeValue[List[str]]] = (
        None  # list of method names, e.g. ["local", "line", "enable"] or ["group"] with group reference
    )
    if_authenticated: Optional[AttributeValue[bool]] = None
    privilege_level: Optional[int] = None  # Only for commands


class CiscoAaaAccountingAttributes(AugmentAttributes):
    type: Literal["cisco_pre_accounting"] = "cisco_pre_accounting"
    name: Optional[AttributeValue[str]] = None  # default, CONSOLE, etc.
    cli_list_name: Optional[str] = (
        None  # if not provided, derived from name (e.g. CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST_2 -> CONSOLE-CUSTOM-COMMAND-AUTHORIZATION-LIST)
    )
    account_type: Optional[AttributeValue[str]] = (
        None  # = Literal['exec', 'commands', 'identity']
    )
    group_type: Optional[AttributeValue[str]] = None  # = Literal['tacacs+', 'radius']
    methods: Optional[AttributeValue[List[str]]] = None
    privilege_level: Optional[int] = None  # Only for commands


class CiscoConsoleAaaAttributes(AugmentAttributes):
    # Examples:
    # authorization commands 15 CONSOLE-COMMANDS
    # authorization exec CONSOLE-EXEC
    # login authentication CONSOLE-AUTHENTICATION
    type: Literal["cisco_console_aaa"] = "cisco_console_aaa"
    name: Optional[AttributeValue[str]] = None
    login_authentication: Optional[AttributeValue[str]] = None#Optional[Reference] = None
    authorization_exec: Optional[AttributeValue[str]] = None#Optional[Reference] = None
    authorization_commands: Optional[AttributeValue[str]] = None#Optional[Reference] = None


class CiscoVtyAaaAttributes(AugmentAttributes):
    # Examples:
    # line vty 0 4
    # login authentication VTY-AUTH
    # authorization exec VTY-EXEC-AUTH
    type: Literal["cisco_vty_aaa"] = "cisco_vty_aaa"
    name: Optional[AttributeValue[str]] = None
    login_authentication: Optional[AttributeValue[str]] = None#Optional[Reference] = None
    authorization_exec: Optional[AttributeValue[str]] = None#Optional[Reference] = None


class CiscoConsoleAaa(Augment):
    """
    AAA configuration for console lines.
    Ex. command:
    aaa authentication login CONSOLE-COMMANDS group ISE-TACACS+ local
    authorization commands 0 CONSOLE-COMMANDS
    """
    type = "cisco_console_aaa"
    model_cls = CiscoConsoleAaaAttributes
    valid_targets = (Console,)
    default_vendor = "cisco"
    singleton = False

class CiscoVtyAaa(Augment):
    """
    AAA configuration for VTY lines.
    Ex. command:
    line vty 0 4
    login authentication VTY-AUTH
    authorization exec VTY-EXEC-AUTH
    """
    type = "cisco_vty_aaa"
    model_cls = CiscoVtyAaaAttributes
    valid_targets = (VtyLine,)
    default_vendor = "cisco"
    singleton = False

class CiscoAaaAuthentication(Augment):
    """
    Authentication method list for login or enable.
    Ex. command:
    aaa authentication login default group ISE-TACACS+ local line enable.
    """

    type = "cisco_aaa_authentication"
    model_cls = CiscoAaaAuthenticationAttributes
    valid_targets = (aaaAuthenticationConfig,)
    default_vendor = "cisco"
    singleton = False

    def pre_init(self):
        if self.kwargs.get("cli_list_name") is None:
            self.kwargs["cli_list_name"] = _derive_cli_list_name(
                self.kwargs.get("name")
            )
        if (
            self.kwargs.get("group_name") is not None
            and self.kwargs.get("group_type") is not None
        ):
            group = self.kwargs.pop("group_name")
            if self.kwargs.get("group_type") == "tacacs+":
                if isinstance(group, aaaServerGroup):
                    #group = self.kwargs.pop("group_name")
                    self.kwargs["group"] = ReferenceTo(
                        pointer=f"system.aaa.server_groups.{group.name}.tacacs"
                    )
                if isinstance(group, str):
                    #group_name = self.kwargs.pop("group_name")
                    self.kwargs["group"] = Reference(
                        pointer=f"system.aaa.server_groups.{group}.tacacs"
                    )
            if self.kwargs.get("group_type") == "radius":
                if isinstance(group, aaaServerGroup):
                    #group = self.kwargs.pop("group_name")
                    self.kwargs["group"] = ReferenceTo(
                        pointer=f"system.aaa.server_groups.{group.name}.radius"
                    )
                if isinstance(group, str):
                    #group_name = self.kwargs.pop("group_name")
                    self.kwargs["group"] = Reference(
                        pointer=f"system.aaa.server_groups.{group}.radius"
                    )
        super().pre_init()


class CiscoAaaAuthorization(Augment):
    """
    Authorization method list for exec or commands.
    Ex. command:
    aaa authorization exec default group ISE-TACACS+ local line enable.
    """

    type = "cisco_aaa_authorization"
    model_cls = CiscoAaaAuthorizationAttirbutes
    valid_targets = (aaaAuthorizationConfig,)
    default_vendor = "cisco"
    singleton = False

    def pre_init(self):
        if self.kwargs.get("cli_list_name") is None:
            self.kwargs["cli_list_name"] = _derive_cli_list_name(
                self.kwargs.get("name")
            )
        if (
            self.kwargs.get("group_name") is not None
            and self.kwargs.get("group_type") is not None
        ):
            group = self.kwargs.pop("group_name")
            if self.kwargs.get("group_type") == "tacacs+":
                if isinstance(group, aaaServerGroup):
                    #group = self.kwargs.pop("group_name")
                    self.kwargs["group"] = ReferenceTo(
                        pointer=f"system.aaa.server_groups.{group.name}.tacacs"
                    )
                if isinstance(group, str):
                    #group_name = self.kwargs.pop("group_name")
                    self.kwargs["group"] = Reference(
                        pointer=f"system.aaa.server_groups.{group}.tacacs"
                    )
            if self.kwargs.get("group_type") == "radius":
                if isinstance(group, aaaServerGroup):
                    #group = self.kwargs.pop("group_name")
                    self.kwargs["group"] = ReferenceTo(
                        pointer=f"system.aaa.server_groups.{group.name}.radius"
                    )
                if isinstance(group, str):
                    #group_name = self.kwargs.pop("group_name")
                    self.kwargs["group"] = Reference(
                        pointer=f"system.aaa.server_groups.{group}.radius"
                    )
        super().pre_init()


class CiscoAaaAccounting(Augment):
    """
    Accounting method list for login or enable.
    Ex. command:
    aaa accounting login default group ISE-TACACS+ local line enable.
    """

    type = "cisco_aaa_accounting"
    model_cls = CiscoAaaAccountingAttributes
    valid_targets = (aaaAccountingConfig,)
    default_vendor = "cisco"
    singleton = False

    def pre_init(self):
        if self.kwargs.get("cli_list_name") is None:
            self.kwargs["cli_list_name"] = _derive_cli_list_name(
                self.kwargs.get("name")
            )
        if (
            self.kwargs.get("group_name") is not None
            and self.kwargs.get("group_type") is not None
        ):
            group = self.kwargs.pop("group_name")
            if self.kwargs.get("group_type") == "tacacs+":
                if isinstance(group, aaaServerGroup):
                    #group = self.kwargs.pop("group_name")
                    self.kwargs["group"] = ReferenceTo(
                        pointer=f"system.aaa.server_groups.{group.name}.tacacs"
                    )
                if isinstance(group, str):
                    #group_name = self.kwargs.pop("group_name")
                    self.kwargs["group"] = Reference(
                        pointer=f"system.aaa.server_groups.{group}.tacacs"
                    )
            if self.kwargs.get("group_type") == "radius":
                if isinstance(group, aaaServerGroup):
                    #group = self.kwargs.pop("group_name")
                    self.kwargs["group"] = ReferenceTo(
                        pointer=f"system.aaa.server_groups.{group.name}.radius"
                    )
                if isinstance(group, str):
                    #group_name = self.kwargs.pop("group_name")
                    self.kwargs["group"] = Reference(
                        pointer=f"system.aaa.server_groups.{group}.radius"
                    )
        super().pre_init()
