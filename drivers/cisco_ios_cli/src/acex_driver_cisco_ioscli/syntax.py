"""Cisco IOS syntax for ComposedConfiguration components. Each block renders and parses the same lines."""

import ipaddress
from typing import Any

from acex_devkit.drivers.mapper import (
    Augment,
    Block,
    Choice,
    Dispatch,
    Flag,
    Keyword,
    Line,
    Mount,
    Multiline,
    Pointer,
    Section,
)
from acex_devkit.drivers.mapper.tokens import Token
from acex_devkit.models.acl_model import AclProtoclOptions, Ipv4AclAttributes, Ipv4AclEntryAttributes
from acex_devkit.models.composed_configuration import (
    DHCPSnoopingAttributes,
    DnsServerAttributes,
    EthernetCsmacdInterface,
    HsrpGroup,
    Ieee8023adLagInterface,
    InterfaceTemplateAttributes,
    L3IpvlanInterface,
    LacpConfig,
    NetworkInstance,
    NtpServer,
    ServicesAttributes,
    SnmpCommunity,
    SnmpSecurityLevel,
    SnmpServer,
    SnmpView,
    SoftwareLoopbackInterface,
    SshServer,
    StaticRouteNextHop,
    StormControlAttributes,
    SubInterface,
    SystemConfig,
    Vlan,
    VrrpGroup,
    VTPAttributes,
    aaaGlobalAttributes,
    aaaRadiusAttributes,
    aaaServerGroupAttributes,
    aaaTacacsAttributes,
    authenticationUser,
)
from acex_devkit.models.logging import Console, LoggingConfig, LoggingSeverity, RemoteServer, VtyLine

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


class AclAddress(Token):
    """An ACL address as IOS writes it, `any`, a host or a network with a wildcard mask, read as
    "any" or an IPv4 network. Extended ACLs mark a host with `host`; standard ACLs write it bare."""

    def __init__(self, host_keyword: bool):
        self.host_keyword = host_keyword
        self.regex = r"any|host \S+|\d+\.\d+\.\d+\.\d+(?: \d+\.\d+\.\d+\.\d+)?"

    def parse(self, text: str) -> Any:
        if text == "any":
            return "any"
        address, _, wildcard = text.removeprefix("host ").partition(" ")
        if not wildcard:
            return ipaddress.IPv4Network(f"{address}/32")
        mask = ipaddress.IPv4Address(int(ipaddress.IPv4Address(wildcard)) ^ 0xFFFFFFFF)
        return ipaddress.IPv4Network(f"{address}/{mask}", strict=False)

    def render(self, value: Any) -> str | None:
        if value == "any":
            return "any"
        network = ipaddress.IPv4Network(value)
        if network.prefixlen == 32:
            return f"host {network.network_address}" if self.host_keyword else str(network.network_address)
        return f"{network.network_address} {network.hostmask}"


class AclPort(Token):
    """A port match, `eq 443` <-> "443" and `range 100 200` <-> "100-200"."""

    regex = r"eq \S+|range \S+ \S+"

    def parse(self, text: str) -> str:
        operator, _, ports = text.partition(" ")
        return ports.replace(" ", "-") if operator == "range" else ports

    def render(self, value: str) -> str | None:
        return f"range {value.replace('-', ' ')}" if "-" in value else f"eq {value}"


class LoadBalance(Token):
    """`port-channel load-balance` with one hashing input: `src-dst-ip` <-> ["src-dst-ip"]."""

    regex = r"(?:src|dst|src-dst)-(?:mac|ip|port)"

    def parse(self, text: str) -> list[str]:
        return [text]

    def render(self, value: list[str]) -> str | None:
        return value[0] if len(value) == 1 else None


SEVERITIES = Choice(
    {
        LoggingSeverity.EMERGENCY: "emergencies",
        LoggingSeverity.ALERT: "alerts",
        LoggingSeverity.CRITICAL: "critical",
        LoggingSeverity.ERROR: "errors",
        LoggingSeverity.WARNING: "warnings",
        LoggingSeverity.NOTICE: "notifications",
        LoggingSeverity.INFORMATIONAL: "informational",
        LoggingSeverity.DEBUG: "debugging",
    }
)


class PasswordEncryptionSyntax(Augment):
    path = "system.config.augments"
    augment = "cisco_service_password_encryption"
    body = (Flag("enabled", on="service password-encryption", off="no service password-encryption"),)


class TrapLoggingSyntax(Augment):
    path = "system.logging.config.augments"
    augment = "cisco.trap_logging"
    body = (Line("logging trap {severity}", severity=SEVERITIES),)


class ConsoleLoggingSyntax(Augment):
    path = "system.logging.config.augments"
    augment = "cisco.console_logging"
    body = (Flag("enabled", on="logging console", off="no logging console"),)


class SshLoggingSyntax(Augment):
    path = "system.logging.config.augments"
    augment = "cisco.ssh_logging"
    body = (Flag("enabled", on="ip ssh logging events"),)


class SshDhSyntax(Augment):
    path = "system.ssh.config.augments"
    augment = "cisco_dh_min_size"
    body = (Line("ip ssh dh min size {dh_min_size:int}"),)


class DhcpTrackSyntax(Augment):
    path = "system.dhcp.snooping.augments"
    augment = "cisco_dhcp_snooping_track_server"
    body = (Line("ip dhcp snooping track server[ {all_dhcp_acks}]", all_dhcp_acks=Keyword("all-dhcp-acks")),)


class DeviceTrackingSyntax(Augment):
    path = "augments"
    augment = "cisco_device_tracking_policy"
    body = (Line("device-tracking attach-policy {policy_name}"),)


class ServicePolicySyntax(Augment):
    path = "augments"
    augment = "cisco_service_policy"
    body = (
        Line("service-policy input {input_policy}"),
        Line("service-policy output {output_policy}"),
    )


class LineAaaSyntax(Augment):
    """Login and authorization lists on a console or vty line. Commands are authorized per privilege
    level; one list covers the levels IOS has, so it's written for each."""

    path = "augments"
    body = (
        Line("login authentication {login_authentication}"),
        Line("authorization exec {authorization_exec}"),
        Line("authorization commands 0 {authorization_commands}"),
        Line("authorization commands 1 {authorization_commands}"),
        Line("authorization commands 15 {authorization_commands}"),
    )


class ConsoleAaaSyntax(LineAaaSyntax):
    augment = "cisco_console_aaa"


class VtyAaaSyntax(LineAaaSyntax):
    augment = "cisco_vty_aaa"


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


class TacacsServerSyntax(Block):
    """A TACACS+ server's settings, written once and shared by every group listing it by name."""

    path = "system.aaa.server_groups.{group}.tacacs"
    header = Line("tacacs server {name}")
    key = "name"
    shared = True
    component = aaaTacacsAttributes
    body = (
        Line("address ipv4 {address}"),
        Line("key 7 {secret_key_hashed}"),
        Line("key 0 {secret_key}"),
        Line("port {port:int}"),
        Line("timeout {timeout:int}"),
    )


class RadiusServerSyntax(Block):
    """A RADIUS server's settings, written once and shared by every group listing it by name."""

    path = "system.aaa.server_groups.{group}.radius"
    header = Line("radius server {name}")
    key = "name"
    shared = True
    component = aaaRadiusAttributes
    body = (
        Line("address ipv4 {address}[ auth-port {auth_port:int}][ acct-port {acct_port:int}]"),
        Line("key 7 {secret_key_hashed}"),
        Line("key 0 {secret_key}"),
        Line("timeout {timeout:int}"),
        Line("retransmit {retransmit_attempts:int}"),
    )


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
        Line("source template {interface_template}", interface_template=Pointer("interface_templates")),
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
        Mount("ip dhcp snooping trust", at="system.dhcp.snooping.trust_interfaces"),
        Line("ip address {ipv4:ipv4_mask}"),
        Mount(
            "ip helper-address {server}", at="system.dhcp.relay.relay_servers.{server:address}.interfaces", creates=True
        ),
        DeviceTrackingSyntax(),
        ServicePolicySyntax(),
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


class InterfaceTemplateSyntax(Block):
    """A named set of interface settings, written with the interface lines it shares. Memberships and the
    interface's own defaults don't apply to a template, and a template doesn't name another."""

    path = "interface_templates"
    header = Line("template {name}")
    component = InterfaceTemplateAttributes
    body = tuple(
        entry
        for entry in InterfaceSyntax.body
        if entry.applies_to(InterfaceTemplateAttributes)
        and not isinstance(entry, Mount)
        and not (isinstance(entry, Flag) and entry.default is not None)
        and "interface_template" not in getattr(entry, "fields", ())
    ) + (Flag("enabled", off="shutdown"),)


class StaticRouteSyntax(Block):
    path = "network_instances.{vrf:name}.protocols.static_routes.{prefix}.next_hops"
    key = "next_hop"
    implied = {"vrf": "global"}
    component = StaticRouteNextHop
    body = (Line("ip route[ vrf {vrf}] {prefix:ipv4_mask} {next_hop}[ {metric:int}]"),)


class LoggingSyntax(Block):
    path = "system.logging.config"
    component = LoggingConfig
    # `logging trap` is the cisco.trap_logging augment, which is what config maps set.
    body = (Line("logging buffered {buffer_size:int}"),)


class LoggingHostSyntax(Block):
    path = "system.logging.remote_servers.servers"
    key = "host"
    component = RemoteServer
    body = (Line("logging host {host}[ transport {transport} port {port:int}]", transport=Choice("udp", "tcp")),)


class SnmpCommunitySyntax(Block):
    path = "system.snmp.communities"
    key = "community"
    component = SnmpCommunity
    # Only read-only communities are modelled; RO is what the device writes when none is given.
    body = (Line("snmp-server community {community}[ RO][ {ipv4acl}]", ipv4acl=Pointer("acl.ipv4_acls")),)

    def complete(self, fields: dict[str, Any], position: int, context: Any) -> dict[str, Any]:
        return {"name": fields["community"], **fields}


class SnmpHostSyntax(Block):
    path = "system.snmp.trap_servers"
    key = "address"
    component = SnmpServer
    body = (
        Line(
            "snmp-server host {address}[ vrf {network_instance}] version {version} {community}",
            version=Choice(v2c="2c"),
        ),
        Line(
            "snmp-server host {address}[ vrf {network_instance}] version {version} {security_level} {username}",
            version=Choice(v3="3"),
            security_level=Choice(
                {
                    SnmpSecurityLevel.NO_AUTH_NO_PRIV: "noauth",
                    SnmpSecurityLevel.AUTH_NO_PRIV: "auth",
                    SnmpSecurityLevel.AUTH_PRIV: "priv",
                }
            ),
        ),
    )

    def derive(self, values: dict[str, Any], context: Any) -> dict[str, Any] | None:
        # The default instance is where a host without `vrf` lives; it's never written.
        return {**values, "network_instance": None} if values.get("network_instance") == "global" else values

    def includes(self, key: str | None, component: SnmpServer) -> bool:
        return component.enabled is None or bool(component.enabled.value)


class SnmpViewSyntax(Block):
    path = "system.snmp.views.{view:name}.oids"
    key = "oid"
    component = SnmpView
    body = (Line("snmp-server view {view} {oid} {included}", included=Choice({True: "included", False: "excluded"})),)

    def complete(self, fields: dict[str, Any], position: int, context: Any) -> dict[str, Any]:
        return {"name": fields["oid"], **fields}


class VtpSyntax(Block):
    path = "system.vtp.config"
    component = VTPAttributes
    body = (
        Line("vtp domain {domain_name}"),
        Line("vtp mode {mode}", mode=Choice("server", "client", "transparent", "off")),
        Line("vtp version {version}", version=Choice(1, 2, 3)),
        Line("vtp password {password_hashed} hidden"),
        Line("vtp password {password}"),
    )


class LacpSyntax(Block):
    path = "lacp.config"
    component = LacpConfig
    body = (
        Line("lacp system-priority {system_priority:int}"),
        Line("port-channel load-balance {load_balance_algorithm}", load_balance_algorithm=LoadBalance()),
    )


class DhcpSnoopingSyntax(Block):
    path = "system.dhcp.snooping"
    component = DHCPSnoopingAttributes
    body = (
        Flag("enabled", on="ip dhcp snooping"),
        Line("ip dhcp snooping vlan {vlans:vlans}"),
        Flag("option82", off="no ip dhcp snooping information option"),
    )


class HttpSyntax(Block):
    path = "system.services.config"
    component = ServicesAttributes
    body = (
        Flag("http", on="ip http server", off="no ip http server"),
        Flag("https", on="ip http secure-server", off="no ip http secure-server"),
    )


class ConsoleSyntax(Block):
    path = "system.logging.console"
    header = Line("line con {line_number:int}")
    single = True
    component = Console
    body = (Flag("logging_synchronous", on="logging synchronous"), ConsoleAaaSyntax())


ACTIONS = Choice("permit", "deny")
EXTENDED_FIELDS = ("protocol", "destination_address", "source_port", "destination_port", "log", "dscp")


class StandardAclEntrySyntax(Block):
    path = "acl_entries"
    key = "sequence_id"
    component = Ipv4AclEntryAttributes
    body = (Line("{sequence_id:int} {action} {source_address}", action=ACTIONS, source_address=AclAddress(False)),)


class ExtendedAclEntrySyntax(Block):
    path = "acl_entries"
    key = "sequence_id"
    component = Ipv4AclEntryAttributes
    body = (
        Line(
            "{sequence_id:int} {action} {protocol} {source_address}[ {source_port}]"
            " {destination_address}[ {destination_port}][ {log}]",
            action=ACTIONS,
            protocol=Choice(*AclProtoclOptions),
            source_address=AclAddress(True),
            destination_address=AclAddress(True),
            source_port=AclPort(),
            destination_port=AclPort(),
            log=Keyword("log"),
        ),
    )


class StandardAclSyntax(Block):
    """An IPv4 ACL whose entries match on source only. The model doesn't say standard or extended;
    what its entries match on does."""

    path = "acl.ipv4_acls"
    header = Line("ip access-list standard {name}")
    component = Ipv4AclAttributes
    body = (StandardAclEntrySyntax(),)

    def includes(self, key: str | None, component: Ipv4AclAttributes) -> bool:
        entries = (component.acl_entries or {}).values()
        return not any(getattr(entry, name) is not None for entry in entries for name in EXTENDED_FIELDS)


class ExtendedAclSyntax(StandardAclSyntax):
    header = Line("ip access-list extended {name}")
    body = (ExtendedAclEntrySyntax(),)

    def includes(self, key: str | None, component: Ipv4AclAttributes) -> bool:
        return not super().includes(key, component)


class NameServerSyntax(Block):
    """DNS servers. IOS writes every server of one instance on one line; each renders on its own here,
    which the device merges back into one."""

    path = "system.dns.dns_servers"
    key = "address"
    component = DnsServerAttributes
    body = (Line("ip name-server[ vrf {network_instance}] {address:words}"),)

    def derive(self, values: dict[str, Any], context: Any) -> dict[str, Any] | None:
        # The default instance is where a server without `vrf` lives; it's never written.
        return {**values, "network_instance": None} if values.get("network_instance") == "global" else values


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
        VtyAaaSyntax(),
    )


class NtpServerSyntax(Block):
    path = "system.ntp.servers"
    header = Line("ntp server {address}[ {prefer}]", prefer=Keyword("prefer"))
    component = NtpServer


BLOCKS = [
    PasswordEncryptionSyntax(),
    SystemConfigSyntax(),
    VrfSyntax(),
    AaaSyntax(),
    AaaServerGroupSyntax(),
    TacacsServerSyntax(),
    RadiusServerSyntax(),
    UserSyntax(),
    LoggingSyntax(),
    TrapLoggingSyntax(),
    ConsoleLoggingSyntax(),
    VtpSyntax(),
    DhcpSnoopingSyntax(),
    DhcpTrackSyntax(),
    LacpSyntax(),
    VlanSyntax(),
    InterfaceTemplateSyntax(),
    InterfaceSyntax(),
    HttpSyntax(),
    NameServerSyntax(),
    StaticRouteSyntax(),
    StandardAclSyntax(),
    ExtendedAclSyntax(),
    SshSyntax(),
    SshLoggingSyntax(),
    SshDhSyntax(),
    SnmpCommunitySyntax(),
    SnmpViewSyntax(),
    SnmpHostSyntax(),
    LoggingHostSyntax(),
    ConsoleSyntax(),
    VtyLineSyntax(),
    NtpServerSyntax(),
]
"""Top-level blocks in running-config order."""
