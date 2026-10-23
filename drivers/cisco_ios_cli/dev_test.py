from acex_devkit.models.composed_configuration import (
    ComposedConfiguration,
    EthernetCsmacdInterface,
    System,
    SystemConfig,
)
from acex_driver_cisco_ioscli import CiscoIOSCLIDriver

ned = CiscoIOSCLIDriver()

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

# The codec does not use the node, so a local round-trip runs without one.
out = ned.render(composed_config, None)

print("--- rendered ---")
print(out)

result = ned.parse(out, None)

print("\n--- parsed back ---")
print(result.model_dump_json(indent=2, exclude_none=True))

reparsed_out = ned.render(result, None)

print("\n--- re-rendered from parsed tree ---")
print(reparsed_out)
print("\nround-trip matches:", reparsed_out == out)

print("\n--- capabilities ---")
print(ned.capabilities.model_dump_json(indent=4))
