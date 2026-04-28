from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import (
    NetflowCollectorAttributes,
    NetflowExporterAttributes,
    NetflowRecordAttributes,
    NetflowGlobalConfigAttributes,
    NetflowRecordIpv4Match as NetflowRecordIpv4MatchAttributes,
    NetflowExporterOptions as NetflowExporterOptionsAttributes,
    ReferenceFrom,
)

class NetflowGlobalConfig(ConfigComponent):
    type = "NetflowGlobalConfig"
    model_cls = NetflowGlobalConfigAttributes

class NetflowCollector(ConfigComponent): 
    type = "NetflowCollector"
    model_cls = NetflowCollectorAttributes

class NetflowExporter(ConfigComponent): 
    type = "NetflowExporter"
    model_cls = NetflowExporterAttributes

    def pre_init(self):
        if self.kwargs.get('network_instance') is None:
            self.kwargs["network_instance"] = "global"
        else:
            network_instance = self.kwargs.pop("network_instance")
            self.kwargs["network_instance"] = network_instance.name

class NetflowExporterOptions(ConfigComponent):
    type = "NetflowExporterOptions"
    model_cls = NetflowExporterOptionsAttributes

class NetflowRecord(ConfigComponent): 
    type = "NetflowRecord"
    model_cls = NetflowRecordAttributes

class NetflowRecordIpv4Match(ConfigComponent):
    type = "NetflowRecordIpv4Match"
    model_cls = NetflowRecordIpv4MatchAttributes

    def pre_init(self):
        # Ensure that referenced components are added to the configuration before this component is added
        if self.kwargs.get("netflow_record") is not None:
            netflow_record = self.kwargs.pop("netflow_record")
            self.kwargs["netflow_record"] = netflow_record.name