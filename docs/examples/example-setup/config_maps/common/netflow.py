from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.sampling.netflow import (
    NetflowCollector, 
    NetflowGlobalConfig, 
    NetflowRecord, 
    NetflowExporter, 
    NetflowRecordIpv4Match,
    NetflowExporterOptions
)

# import managmenet-vlan object for reference
from config_maps.common.mgmt_vlan import mgmt_vlan

class NetflowConfigRecord(ConfigMap):
    def compile(self, context):
        netflow_global_config = NetflowGlobalConfig(
            name="netflow_global_config",
            enabled=True
            )
        context.configuration.add(netflow_global_config)

        netflow_collector_1 = NetflowCollector(
            name="te_etm_monitor", 
            cache_inactive=180, 
            cache_active=360
        )
        context.configuration.add(netflow_collector_1)

        netflow_record_global_1 = NetflowRecord(
            name="te_etm_record_v4",
            application_name=True,
            collect_timestamp_absolute_first=True,
            collect_timestamp_absolute_last=True,
            netflow_collector=netflow_collector_1,
        )
        context.configuration.add(netflow_record_global_1)

        netflow_record_ipv4_match_1 = NetflowRecordIpv4Match(
            name="te_etm_record_v4_match_1",
            netflow_record=netflow_record_global_1,
            protocol=True,
            version=True
        )
        context.configuration.add(netflow_record_ipv4_match_1)

        netflow_exporter_1 = NetflowExporter(
            name='te_etm_exporter',
            address='10.11.123.12',
            port=18089,
            netflow_format="IPFIX",
            source_interface=mgmt_vlan.mgmt_svi,
            netflow_collector=netflow_collector_1,
        )
        context.configuration.add(netflow_exporter_1)

        netflow_exporter_options_1 = NetflowExporterOptions(
            name="te_etm_exporter_options_1",
            interface_table_timeout=300,
            vrf_table_timeout=300,
            sampler_table=True,
            application_table_timeout=300,
            application_attributes_timeout=300,
            netflow_exporter=netflow_exporter_1
        )
        context.configuration.add(netflow_exporter_options_1)

netflowconfigrecord = NetflowConfigRecord()
netflowconfigrecord.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)