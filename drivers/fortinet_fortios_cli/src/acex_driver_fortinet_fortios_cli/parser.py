import ipaddress

from acex_devkit.drivers import ParserBase
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    DnsServerAttributes,
    EthernetCsmacdInterface,
    L3IpvlanInterface,
    ManagementInterface,
    NtpServer,
    SoftwareLoopbackInterface,
    SystemConfig,
)


def _parse_blocks(text: str) -> dict:
    """Parse FortiOS hierarchical config into a nested dict."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    root: dict = {}
    _parse_block_lines(lines, 0, root)
    return root


def _parse_block_lines(lines: list[str], pos: int, out: dict) -> int:
    """Consume lines into *out* recursively, return next position."""
    while pos < len(lines):
        raw = lines[pos]
        stripped = raw.strip()
        pos += 1

        if not stripped or stripped.startswith("#"):
            continue

        parts = stripped.split()
        keyword = parts[0].lower()

        if keyword == "config" and len(parts) > 1:
            section = " ".join(parts[1:])
            section_dict: dict = {}
            pos = _parse_block_lines(lines, pos, section_dict)
            # Merge if section appeared more than once (e.g. nested ntp config)
            if section in out:
                out[section].update(section_dict)
            else:
                out[section] = section_dict

        elif keyword == "edit" and len(parts) > 1:
            entry_id = " ".join(parts[1:]).strip('"')
            entry_dict: dict = {}
            pos = _parse_block_lines(lines, pos, entry_dict)
            out.setdefault("_entries", {})[entry_id] = entry_dict

        elif keyword == "set" and len(parts) > 1:
            key = parts[1]
            values = parts[2:]
            out[key] = " ".join(values) if values else ""

        elif keyword in ("next", "end"):
            break  # caller resumes from pos

    return pos


def _mask_to_cidr(ip: str, mask: str) -> str | None:
    """Convert ``'10.0.0.1' '255.255.255.0'`` → ``'10.0.0.1/24'``."""
    try:
        prefix = ipaddress.IPv4Network(f"0.0.0.0/{mask}", strict=False).prefixlen
        return f"{ip}/{prefix}"
    except ValueError:
        return None


def _parse_ip_mask(value: str) -> str | None:
    """Parse ``'10.0.0.1 255.255.255.0'`` from a single ``set ip`` value."""
    parts = value.split()
    if len(parts) == 2:
        return _mask_to_cidr(parts[0], parts[1])
    if len(parts) == 1 and "/" in parts[0]:
        return parts[0]
    return None


class FortiOSCLIParser(ParserBase):
    def __init__(self):
        self._cfg = ComposedConfiguration()

    def parse(self, configuration: str) -> ComposedConfiguration:
        blocks = _parse_blocks(configuration)
        self._parse_system_global(blocks.get("system global") or {})
        self._parse_system_dns(blocks.get("system dns") or {})
        self._parse_system_ntp(blocks.get("system ntp") or {})
        self._parse_interfaces(blocks.get("system interface") or {})
        self._parse_static_routes(blocks.get("router static") or {})
        return self._cfg

    def _parse_system_global(self, block: dict) -> None:
        hostname = block.get("hostname", "").strip('"') or None
        domain = block.get("domain", "").strip('"') or None
        location = block.get("location", "").strip('"') or None
        contact = block.get("admin-maintainer", "").strip('"') or None

        self._cfg.system.config = SystemConfig(
            hostname=AttributeValue(value=hostname) if hostname else None,
            domain_name=AttributeValue(value=domain) if domain else None,
            location=AttributeValue(value=location) if location else None,
            contact=AttributeValue(value=contact) if contact else None,
        )

    def _parse_system_dns(self, block: dict) -> None:
        servers: dict[str, Any] = {}
        primary = block.get("primary", "").strip()
        secondary = block.get("secondary", "").strip()
        if primary and primary != "0.0.0.0":
            servers["DNS Server 1"] = DnsServerAttributes(
                address=AttributeValue(value=primary)
            )
        if secondary and secondary != "0.0.0.0":
            servers["DNS Server 2"] = DnsServerAttributes(
                address=AttributeValue(value=secondary)
            )
        if servers:
            self._cfg.system.dns.dns_servers = servers

    def _parse_system_ntp(self, block: dict) -> None:
        if block.get("ntpsync", "").lower() != "enable":
            return
        ntp_servers: dict[str, NtpServer] = {}
        entries = (block.get("ntpserver") or {}).get("_entries") or {}
        for _idx, entry in entries.items():
            server = entry.get("server", "").strip('"')
            if not server:
                continue
            prefer = entry.get("ntpv3", "").lower() == "enable"
            ntp_servers[server] = NtpServer(
                address=AttributeValue(value=server),
                prefer=AttributeValue(value=prefer) if prefer else None,
            )
        if ntp_servers:
            self._cfg.system.ntp.servers = ntp_servers

    def _parse_interfaces(self, block: dict) -> None:
        entries = block.get("_entries") or {}
        interfaces: dict = {}
        for idx, (name, entry) in enumerate(entries.items()):
            intf_type = entry.get("type", "physical").lower()
            description = entry.get("alias", "").strip('"') or None
            status = entry.get("status", "up").lower()
            enabled = status != "down"
            ip_raw = entry.get("ip", "")
            ipv4 = _parse_ip_mask(ip_raw) if ip_raw else None
            if ipv4 and ipv4.startswith("0.0.0.0"):
                ipv4 = None
            mtu_raw = entry.get("mtu-override", "")
            mtu_val = entry.get("mtu", "")
            mtu = int(mtu_val) if mtu_raw.lower() == "enable" and mtu_val.isdigit() else None

            common = dict(
                index=idx,
                name=AttributeValue(value=name),
                description=AttributeValue(value=description) if description else None,
                enabled=AttributeValue(value=enabled),
                ipv4=AttributeValue(value=ipv4) if ipv4 else None,
                mtu=AttributeValue(value=mtu) if mtu else None,
            )

            if intf_type == "loopback":
                interfaces[name] = SoftwareLoopbackInterface(**common)
            elif intf_type == "vlan":
                vlan_id = int(entry.get("vlanid", 0)) or None
                parent = entry.get("interface", "").strip('"') or None
                interfaces[name] = L3IpvlanInterface(
                    **common,
                    vlan_id=AttributeValue(value=vlan_id) if vlan_id else None,
                    parent_interface=AttributeValue(value=parent) if parent else None,
                )
            elif name == "mgmt" or name.startswith("mgmt"):
                interfaces[name] = ManagementInterface(**common)
            else:
                interfaces[name] = EthernetCsmacdInterface(**common)

        if interfaces:
            self._cfg.interfaces.update(interfaces)

    def _parse_static_routes(self, block: dict) -> None:
        from acex_devkit.models.composed_configuration import (
            NetworkInstance,
            Protocols,
            StaticRoute,
            StaticRouteNextHop,
        )

        entries = block.get("_entries") or {}
        routes: dict = {}
        for _seq, entry in entries.items():
            dst = entry.get("dst", "").strip()
            gateway = entry.get("gateway", "").strip()
            if not dst or not gateway or gateway == "0.0.0.0":
                continue
            dst_cidr = _parse_ip_mask(dst) or dst
            route_key = dst_cidr.replace("/", "_").replace(".", "_")
            routes[route_key] = StaticRoute(
                name=AttributeValue(value=route_key),
                prefix=AttributeValue(value=dst_cidr),
                next_hops={
                    "nh0": StaticRouteNextHop(
                        name=AttributeValue(value="nh0"),
                        next_hop=AttributeValue(value=gateway),
                    )
                },
            )

        if routes:
            ni = self._cfg.network_instances.setdefault(
                "global", NetworkInstance(name=AttributeValue(value="global"))
            )
            if ni.protocols is None:
                ni.protocols = Protocols()
            ni.protocols.static_routes = routes

