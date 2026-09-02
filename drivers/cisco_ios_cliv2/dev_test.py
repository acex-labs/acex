import json

from acex_devkit.models.asset import Asset
from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    EthernetCsmacdInterface,
    System,
    SystemConfig,
)
from acex_driver_cisco_ioscliv2 import CiscoIOSCLIDriverV2

ned = CiscoIOSCLIDriverV2()

asset = Asset(
    vendor="cisco",
    serial_number="FTX12345678",
    os="ios",
    os_version="15.2.7",
    hardware_model="C9300-24T",
    ned_id="cisco_ios_cliv2",
)

interface = EthernetCsmacdInterface(
    index=1,
    name="GigabitEthernet0/1",
    description="Uplink to core switch",
    enabled=True,
)
interface2 = EthernetCsmacdInterface(
    index=2,
    name="GigabitEthernet0/2",
    enabled=False,
)

composed_config = ComposedConfiguration(
    system=System(
        config=SystemConfig(hostname="SW1", domain_name="ip.com", motd_banner="Hej\nthis is restricted\nkeep out")
    ),
    interfaces={
        "GigabitEthernet0/1": interface,
        "GigabitEthernet0/2": interface2,
    },
)


out = ned.render(composed_config, asset)

print("--- rendered ---")
print(out)

# Round-trip through the driver's own public interface only (render/parse) — the
# SyntaxSpec/Mapper concept lives behind CiscoIOSCLIRenderer/CiscoIOSCLIParser, not something a
# consumer of the driver needs to know about. See
# /Users/johan/.claude/plans/validated-finding-petal.md. Only interfaces are covered so far.
result = ned.parse(out)

print("\n--- parsed back ---")
print("hostname=", result.get("system", {}).get("config", {}).get("hostname", {}).get("value"))
for name, intf in result["interfaces"].items():
    print(
        name,
        "description=",
        intf.get("description", {}).get("value"),
        "enabled=",
        intf.get("enabled", {}).get("value"),
    )

reconstructed = ComposedConfiguration(**result)
reparsed_out = ned.render(reconstructed, asset)

print("\n--- re-rendered from parsed tree ---")
print(reparsed_out)
print("\nround-trip matches:", reparsed_out == out)

print("\r\n")


print(json.dumps(ned.capabilities, indent=4))
