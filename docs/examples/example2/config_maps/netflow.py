from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.sampling.netflow import (
    NetflowCollector, 
    NetflowGlobalConfig, 
    NetflowRecord, 
    NetflowExporter, 
    NetflowRecordIpv4Match,
    NetflowExporterOptions
)
from acex.configuration.components.interfaces import FrontpanelPort, Svi
from acex.configuration.components.vlan import Vlan
from acex.configuration.components.network_instances import L3Vrf
from config_maps.system.mgmt_vlan import mgmt_vlan

class NetflowConfigRecord(ConfigMap):
    def compile(self, context):
        netflow_global_config = NetflowGlobalConfig(
            name="netflow_global_config_123",
            enabled=True
            )
        context.configuration.add(netflow_global_config)

        netflow_record_global_1 = NetflowRecord(
            name="netflow_record_global_1",
            collect_timestamp_absolute_first=True,
            collect_timestamp_absolute_last=True,
            application_name=True
        )
        context.configuration.add(netflow_record_global_1)

        netflow_record_ipv4_match_1 = NetflowRecordIpv4Match(
            name="netflow_record_ipv4_match_1",
            netflow_record=netflow_record_global_1,
            protocol=True,
            length=True
        )
        context.configuration.add(netflow_record_ipv4_match_1)

        test_vrf = L3Vrf(
            name="test",
        )
        context.configuration.add(test_vrf)

        vlan123 = Vlan(
            name="vlan123",
            vlan_name="vlan123",
            vlan_id=123,
        )
        context.configuration.add(vlan123)

        svi123 = Svi(
            name="svi123",
            index=0,
            vlan=vlan123,
            network_instance=test_vrf
        )
        context.configuration.add(svi123)

        netflow_exporter_1 = NetflowExporter(
            name='netflow_exporter_123',
            address='123.123.123.123',
            port=123,
            netflow_format="IPFIX",
            source_interface=svi123,
            network_instance=test_vrf,
        )
        context.configuration.add(netflow_exporter_1)

        netflow_exporter_options_1 = NetflowExporterOptions(
            name="netflow_exporter_options_1",
            interface_table_timeout=300,
            vrf_table_timeout=300,
            sampler_table=True,
            application_table_timeout=300,
            application_attributes_timeout=300,
            netflow_exporter=netflow_exporter_1
        )
        context.configuration.add(netflow_exporter_options_1)

        netflow_collector_1 = NetflowCollector(
            name='netflow_collector_123',
            netflow_exporter=netflow_exporter_1,
            netflow_record=netflow_record_global_1,
            cache_inactive=180,
            cache_active=360
        )
        context.configuration.add(netflow_collector_1)

        intf1_1 = FrontpanelPort(
            name="1/1",
            index=131073,
            network_instance=test_vrf,
            netflow_ingress_disabled=netflow_collector_1,
            netflow_egress_disabled=netflow_collector_1
        )
        context.configuration.add(intf1_1)

netflowconfigrecord = NetflowConfigRecord()
netflowconfigrecord.filters = FilterAttribute("site").eq("/.*/")