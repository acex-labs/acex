from acex_devkit.models.asset import Asset
from acex_devkit.models.composed_configuration import ComposedConfiguration, EthernetCsmacdInterface
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

composed_config = ComposedConfiguration(
    interfaces={"GigabitEthernet0/1": interface},
)


out = ned.render(composed_config, asset)

print(out)
