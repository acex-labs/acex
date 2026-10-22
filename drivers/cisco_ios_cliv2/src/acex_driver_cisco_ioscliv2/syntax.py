"""Cisco IOS syntax for ComposedConfiguration components. Each block renders and parses the same lines."""

from typing import Any

from acex_devkit.drivers.mapper import Block, Choice, Dispatch, Flag, Keyword, Line, Mount, Multiline, Pointer, Section
from acex_devkit.drivers.mapper.tokens import Token
from acex_devkit.models.composed_configuration import (
    EthernetCsmacdInterface,
    Ieee8023adLagInterface,
    L3IpvlanInterface,
    NetworkInstance,
    NtpServer,
    SoftwareLoopbackInterface,
    SshServer,
    StormControlAttributes,
    SubInterface,
    SystemConfig,
    aaaGlobalAttributes,
    aaaRadiusAttributes,
    aaaServerGroupAttributes,
    aaaTacacsAttributes,
)


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
        Line("ip domain name {domain_name}"),
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

    def complete(self, fields: dict[str, Any], position: int) -> dict[str, Any]:
        return {"enable": True, **fields}

    def includes(self, key: str | None, component: aaaServerGroupAttributes) -> bool:
        return bool(component.enable and component.enable.value)


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
        Line("mtu {mtu:int}"),
        Line("speed {speed:int}"),
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

    def complete(self, fields: dict[str, Any], position: int) -> dict[str, Any]:
        return {"index": position, **fields}


class SshSyntax(Block):
    path = "system.ssh.config"
    component = SshServer
    body = (
        Line("ip ssh version {protocol_version:int}"),
        Line("ip ssh time-out {timeout:int}"),
        Line("ip ssh authentication-retries {auth_retries:int}"),
        Line("ip ssh source-interface {source_interface}", source_interface=Pointer("interfaces")),
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
    InterfaceSyntax(),
    SshSyntax(),
    NtpServerSyntax(),
]
"""Top-level blocks in running-config order."""
