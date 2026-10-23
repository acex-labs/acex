"""Cisco IOS syntax for ComposedConfiguration components. Each block renders and parses the same lines."""

from typing import Any

from acex_devkit.drivers.mapper import Block, Choice, Dispatch, Flag, Keyword, Line, Mount, Multiline, Pointer, Section
from acex_devkit.drivers.mapper.tokens import Token
from acex_devkit.models.composed_configuration import (
    EthernetCsmacdInterface,
    HsrpGroup,
    Ieee8023adLagInterface,
    L3IpvlanInterface,
    NetworkInstance,
    NtpServer,
    SoftwareLoopbackInterface,
    SshServer,
    StaticRouteNextHop,
    StormControlAttributes,
    SubInterface,
    SystemConfig,
    Vlan,
    VrrpGroup,
    aaaGlobalAttributes,
    aaaRadiusAttributes,
    aaaServerGroupAttributes,
    aaaTacacsAttributes,
    authenticationUser,
)
from acex_devkit.models.logging import VtyLine

from acex_driver_cisco_ioscli.context import CiscoContext


class Pps(Token):
    """A packet rate as IOS writes it, with a `k` or `m` suffix on round numbers: `2k` <-> 2000."""

    regex = r"\d+[km]?"
    units = {"k": 1_000, "m": 1_000_000}

    def parse(self, text: str) -> int:
        return int(text[:-1]) * self.units[text[-1]] if text[-1] in self.units else int(text)

    def render(self, value: int) -> str | None:
        for suffix, unit in reversed(self.units.items()):
            if value >= unit and value % unit == 0:
                return f"{value // unit}{suffix}"
        return str(value)


class SystemConfigSyntax(Block):
    path = "system.config"
    component = SystemConfig
    body = (
        Line("hostname {hostname}"),
        # IOS-XE 16 renamed the command; each release writes it only its own way.
        Line("ip domain-name {domain_name}", until="16"),
        Line("ip domain name {domain_name}", since="16"),
        Line("ip default-gateway {default_gateway}"),
        Line("snmp-server contact {contact:rest}"),
        Line("snmp-server location {location:rest}"),
        Multiline("login_banner", "banner login {delim}"),
        Multiline("motd_banner", "banner motd {delim}"),
    )


class VrfSyntax(Block):
    path = "network_instances"
    header = Line("vrf definition {name}")
    component = NetworkInstance
    body = (
        Line("description {description:rest}"),
        Section("address-family ipv4", footer="exit-address-family", always=True),
        Section("address-family ipv6", footer="exit-address-family", always=True),
    )

    def includes(self, key: str | None, component: NetworkInstance) -> bool:
        return key != "global"  # the default instance has no syntax of its own


class AaaSyntax(Block):
    path = "system.aaa.config"
    component = aaaGlobalAttributes
    body = (Flag("enabled", on="aaa new-model", off="no aaa new-model"),)


class AaaTacacsMemberSyntax(Block):
    path = "tacacs"
    header = Line("server name {name}")
    component = aaaTacacsAttributes
    when = {"type": "tacacs"}


class AaaRadiusMemberSyntax(Block):
    path = "radius"
    header = Line("server name {name}")
    component = aaaRadiusAttributes
    when = {"type": "radius"}


class AaaServerGroupSyntax(Block):
    path = "system.aaa.server_groups"
    header = Line("aaa group server {type} {name}", type=Choice(tacacs="tacacs+", radius="radius"))
    key = "name"
    component = aaaServerGroupAttributes
    body = (AaaTacacsMemberSyntax(), AaaRadiusMemberSyntax())

    def complete(self, fields: dict[str, Any], position: int, context: Any) -> dict[str, Any]:
        return {"enable": True, **fields}

    def includes(self, key: str | None, component: aaaServerGroupAttributes) -> bool:
        return bool(component.enable and component.enable.value)


class UserSyntax(Block):
    path = "system.aaa.authentication.users"
    header = Line(
        "username {username}[ privilege {privilege:int}]"
        "[ {password_hash_type} {password_hashed}][ secret 0 {password}]",
        # `secret` takes a one-way hash; `password 7` is IOS's reversible scheme.
        password_hash_type=Choice({5: "secret 5", 8: "secret 8", 9: "secret 9", 7: "password 7"}),
    )
    component = authenticationUser


class VlanSyntax(Block):
    path = "network_instances.global.vlans"
    header = Line("vlan {vlan_id:int}")
    component = Vlan
    body = (Line("name {vlan_name:rest}"),)

    def complete(self, fields: dict[str, Any], position: int, context: Any) -> dict[str, Any]:
        return {"name": str(fields["vlan_id"]), **fields}  # the model's own name; the device's is vlan_name


class HsrpSyntax(Block):
    path = "hsrp_groups"
    key = "group"
    component = HsrpGroup
    body = (
        Line("standby {group:int} ip {virtual_address}"),
        Line("standby {group:int} priority {priority:int}"),
        Line("standby {group:int} {preempt}", preempt=Keyword("preempt")),
    )


class VrrpSyntax(Block):
    """IOS VRRP (version 2). Preemption is on by default, so the device writes only turning it off."""

    path = "vrrp_groups"
    key = "group"
    component = VrrpGroup
    body = (
        Line("vrrp {group:int} ip {virtual_address}"),
        Line("vrrp {group:int} priority {priority:int}"),
        Line("vrrp {group:int} {preempt}", preempt=Choice({True: "preempt"})),
        Line("no vrrp {group:int} {preempt}", preempt=Choice({False: "preempt"})),
    )


class StormControlSyntax(Block):
    path = "storm_control"
    component = StormControlAttributes
    body = (
        Line("storm-control broadcast level pps {broadcast_pps}", broadcast_pps=Pps()),
        Line("storm-control multicast level pps {multicast_pps}", multicast_pps=Pps()),
        Line("storm-control unknown-unicast level pps {unknown_unicast_pps}", unknown_unicast_pps=Pps()),
        Line("storm-control action {action}", action=Choice("trap", "shutdown")),
    )


class InterfaceSyntax(Block):
    path = "interfaces"
    header = Line("interface {name}")
    component = Dispatch(
        "name",
        {
            r"\.\d+$": SubInterface,
            r"^Vlan\d+$": L3IpvlanInterface,
            r"^Port-channel\d+$": Ieee8023adLagInterface,
            r"^Loopback\d+$": SoftwareLoopbackInterface,
            r"": EthernetCsmacdInterface,
        },
    )
    body = (
        Line("description {description:rest}"),
        Line("encapsulation dot1Q {vlan_id:int}", only=SubInterface),
        Flag("switchport", on="switchport", off="no switchport"),
        Line("switchport mode {switchport_mode}", switchport_mode=Choice("access", "trunk")),
        Line("switchport access vlan {access_vlan:int}"),
        Line("switchport voice vlan {voice_vlan:int}"),
        Line("switchport trunk native vlan {native_vlan:int}"),
        Line("switchport trunk allowed vlan {trunk_allowed_vlans:vlans}"),
        Flag("dtp_negotiation", off="switchport nonegotiate"),
        # vrf forwarding clears the interface's addresses on IOS, so it renders before them.
        Mount("vrf forwarding {vrf}", at="network_instances.{vrf}.interfaces", default={"vrf": "global"}),
        Line("ip address {ipv4:ipv4_mask}"),
        Flag("redirects", off="no ip redirects"),
        Flag("proxy_arp", off="no ip proxy-arp"),
        HsrpSyntax(),
        VrrpSyntax(),
        Line("mtu {mtu:int}"),
        Line("duplex {duplex}", duplex=Choice("full", "half", "auto")),
        Flag("negotiation", on="negotiation auto", off="no negotiation auto"),
        Flag("auto_mdix", off="no mdix auto"),
        Line(
            "channel-group {aggregate_id:int} mode {lacp_mode}",
            lacp_mode=Choice("active", "passive", "on", "auto"),
        ),
        Line("lacp port-priority {lacp_port_priority:int}"),
        Line("lacp rate {lacp_interval}", lacp_interval=Choice(fast="fast", slow="normal")),
        StormControlSyntax(),
        Line("spanning-tree port-priority {stp_port_priority:int}"),
        Line("spanning-tree cost {stp_cost:int}"),
        Flag("stp_portfast", on="spanning-tree portfast"),
        Flag("stp_bpdu_guard", on="spanning-tree bpduguard enable", off="spanning-tree bpduguard disable"),
        Flag("stp_bpdu_filter", on="spanning-tree bpdufilter enable", off="spanning-tree bpdufilter disable"),
        Flag("stp_loop_guard", on="spanning-tree guard loop"),
        Flag("stp_root_guard", on="spanning-tree guard root"),
        Line("spanning-tree link-type {stp_link_type}", stp_link_type=Choice("point-to-point", "shared")),
        Flag("logging_link_status", off="no logging event link-status"),
        Flag("snmp_link_status_trap", off="no snmp trap link-status"),
        Flag("enabled", on="no shutdown", off="shutdown", default=True),
    )

    def derive(self, values: dict[str, Any], context: CiscoContext) -> dict[str, Any] | None:
        """Loopbacks, SVIs and port-channels are named by their number, physical ports by their place on the
        hardware. Subinterfaces and management ports keep the name the model gives them."""
        if values["type"] == "softwareLoopback":
            return {**values, "name": f"Loopback{values['index']}"}
        if values["type"] == "l3ipvlan":
            return {**values, "name": f"Vlan{values['vlan_id']}"} if values.get("vlan_id") is not None else None
        if values["type"] == "ieee8023adLag":
            aggregate = values.get("aggregate_id")
            return {**values, "name": f"Port-channel{aggregate}"} if aggregate is not None else None
        if values["type"] == "ethernetCsmacd" and context.naming.known:
            name = context.naming.name(values)
            return None if name is None else {**values, "name": name}
        return values

    def complete(self, fields: dict[str, Any], position: int, context: CiscoContext) -> dict[str, Any]:
        name, component_type = str(fields["name"]), self.type_for(fields)
        derived: dict[str, Any] = {}
        if component_type is SoftwareLoopbackInterface:
            derived = {"index": int(name.removeprefix("Loopback"))}
        elif component_type is L3IpvlanInterface:
            derived = {"vlan_id": int(name.removeprefix("Vlan"))}
        elif component_type is Ieee8023adLagInterface:
            derived = {"aggregate_id": int(name.removeprefix("Port-channel"))}
        elif component_type is EthernetCsmacdInterface:
            derived = context.naming.position(name) or {}
        return {"index": position, **fields, **derived}


class StaticRouteSyntax(Block):
    path = "network_instances.{vrf:name}.protocols.static_routes.{prefix}.next_hops"
    key = "next_hop"
    implied = {"vrf": "global"}
    component = StaticRouteNextHop
    body = (Line("ip route[ vrf {vrf}] {prefix:ipv4_mask} {next_hop}[ {metric:int}]"),)


class SshSyntax(Block):
    path = "system.ssh.config"
    component = SshServer
    body = (
        Line("ip ssh version {protocol_version:int}"),
        Line("ip ssh time-out {timeout:int}"),
        Line("ip ssh authentication-retries {auth_retries:int}"),
        Line("ip ssh source-interface {source_interface}", source_interface=Pointer("interfaces")),
    )


class VtyLineSyntax(Block):
    path = "system.logging.vty.lines"
    header = Line("line vty {line_number:range}")
    component = VtyLine
    body = (
        Line(
            "access-class {ipv4acl} {acl_direction}",
            ipv4acl=Pointer("acl.ipv4_acls"),
            acl_direction=Choice("in", "out"),
        ),
        Flag("logging_synchronous", on="logging synchronous"),
        Line("transport input {transport_input:rest}"),
    )


class NtpServerSyntax(Block):
    path = "system.ntp.servers"
    header = Line("ntp server {address}[ {prefer}]", prefer=Keyword("prefer"))
    component = NtpServer


BLOCKS = [
    SystemConfigSyntax(),
    VrfSyntax(),
    AaaSyntax(),
    AaaServerGroupSyntax(),
    UserSyntax(),
    VlanSyntax(),
    InterfaceSyntax(),
    StaticRouteSyntax(),
    SshSyntax(),
    VtyLineSyntax(),
    NtpServerSyntax(),
]
"""Top-level blocks in running-config order."""
