"""The Kea DHCPv4 config for ZTP, rendered from the vendor class mapping, the default method and the DHCP scopes.

Each method a device can be given becomes a client class whose test matches the vendor classes
(option 60) mapped to it, carrying the options that point the device to the method's bootstrap.
The default method's class takes the devices no other class matched. Boot options are only ever
on classes, so scopes carry nothing but addressing.
"""

from acex.ztp.bootstrap import BOOTSTRAPS
from acex_devkit.models.ztp import ZtpDhcpScopeResponse, ZtpVendorClassMatch, ZtpVendorClassResponse

#: Kea's built-in class every packet belongs to.
EVERY_CLIENT = "member('ALL')"
VALID_LIFETIME = 3600


class KeaConfigRenderer:
    def __init__(self, methods, vendor_classes, dhcp_scopes):
        self.methods = methods
        self.vendor_classes = vendor_classes
        self.dhcp_scopes = dhcp_scopes

    def render(self, base_url: str) -> dict:
        """The full config; bootstrap URLs point to the acex at `base_url`."""
        return {
            "Dhcp4": {
                "interfaces-config": {"interfaces": ["*"]},
                "lease-database": {"type": "memfile", "lfc-interval": 3600},
                "valid-lifetime": VALID_LIFETIME,
                "client-classes": self.client_classes(base_url),
                "subnet4": [self.subnet(scope) for scope in self.dhcp_scopes.list_scopes()],
            }
        }

    def client_classes(self, base_url: str) -> list[dict]:
        mapped: dict[str, list[ZtpVendorClassResponse]] = {}
        for vendor_class in self.vendor_classes.list_vendor_classes():
            if vendor_class.method is not None:
                mapped.setdefault(vendor_class.method, []).append(vendor_class)
        classes = [
            self.client_class(f"ztp-{method}", " or ".join(map(self.test, matches)), method, base_url)
            for method, matches in sorted(mapped.items())
        ]
        default = next((m.method for m in self.methods.list_methods() if m.is_default), None)
        if default is not None:
            unmatched = " and ".join(f"not member('{c['name']}')" for c in classes) or EVERY_CLIENT
            classes.append(self.client_class("ztp-default", unmatched, default, base_url))
        return classes

    @staticmethod
    def client_class(name: str, test: str, method: str, base_url: str) -> dict:
        bootstrap = BOOTSTRAPS[method]
        return {"name": name, "test": test, "option-data": bootstrap.dhcp_options(bootstrap.url(base_url))}

    @staticmethod
    def test(vendor_class: ZtpVendorClassResponse) -> str:
        """A Kea expression matching devices that send the vendor class."""
        value = vendor_class.vendor_class
        if vendor_class.match == ZtpVendorClassMatch.prefix:
            return f"substring(option[60].text,0,{len(value.encode())}) == '{value}'"
        return f"option[60].text == '{value}'"

    @staticmethod
    def subnet(scope: ZtpDhcpScopeResponse) -> dict:
        options = [{"name": "routers", "data": str(scope.gateway)}]
        if scope.dns_servers:
            options.append({"name": "domain-name-servers", "data": ", ".join(map(str, scope.dns_servers))})
        if scope.domain_name:
            options.append({"name": "domain-name", "data": scope.domain_name})
        return {
            "id": scope.id,
            "subnet": str(scope.network),
            "pools": [{"pool": f"{scope.pool_start} - {scope.pool_end}"}],
            "option-data": options,
        }


__all__ = ["KeaConfigRenderer"]
