from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import (
    Interface,
    NetflowCollectorAttributes,
    NetflowExporterAttributes,
    NetflowRecordAttributes,
    NetflowGlobalConfigAttributes,
    NetflowRecordIpv4Match as NetflowRecordIpv4MatchAttributes,
    NetflowExporterOptions as NetflowExporterOptionsAttributes,
    ReferenceFrom,
    ReferenceTo,
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

        # Resolve source_interface
        if "source_interface" in self.kwargs:
            si = self.kwargs.pop("source_interface")
            if isinstance(si, type(None)):
                pass
            elif isinstance(si, str):
                ref = ReferenceTo(pointer=f"interfaces.{si}")
                self.kwargs["source_interface"] = ref

            elif isinstance(si, Interface):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["source_interface"] = ref
                
        if self.kwargs.get("netflow_collector") is not None:
            netflow_collector = self.kwargs.pop("netflow_collector")
            self.kwargs["netflow_collector"] = ReferenceFrom(pointer=f"sampling.netflow.collectors.{netflow_collector.name}.exporters")
            

class NetflowExporterOptions(ConfigComponent):
    type = "NetflowExporterOptions"
    model_cls = NetflowExporterOptionsAttributes

    def pre_init(self):
        # Ensure that referenced components are added to the configuration before this component is added
        if self.kwargs.get("netflow_exporter") is not None:
            netflow_exporter = self.kwargs.pop("netflow_exporter")
            self.kwargs["netflow_exporter"] = netflow_exporter.name

class NetflowRecord(ConfigComponent): 
    type = "NetflowRecord"
    model_cls = NetflowRecordAttributes

    def pre_init(self):
        if self.kwargs.get("netflow_collector") is not None:
            netflow_collector = self.kwargs.pop("netflow_collector")
            self.kwargs["netflow_collector"] = ReferenceFrom(pointer=f"sampling.netflow.collectors.{netflow_collector.name}.records")

class NetflowRecordIpv4Match(ConfigComponent):
    type = "NetflowRecordIpv4Match"
    model_cls = NetflowRecordIpv4MatchAttributes

    def pre_init(self):
        # Ensure that referenced components are added to the configuration before this component is added
        if self.kwargs.get("netflow_record") is not None:
            netflow_record = self.kwargs.pop("netflow_record")
            self.kwargs["netflow_record"] = netflow_record.name