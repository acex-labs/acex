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

    def pre_init(self):
        # Ensure that referenced components are added to the configuration before this component is added
        if self.kwargs.get("netflow_record") is not None:
            netflow_record = self.kwargs.pop("netflow_record")
            self.kwargs["netflow_record"] = netflow_record.name

        if self.kwargs.get("netflow_exporter") is not None:
            netflow_exporter = self.kwargs.pop("netflow_exporter")
            self.kwargs["netflow_exporter"] = netflow_exporter.name

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
            print(f"Resolving source_interface for NetflowExporter {self.kwargs}")
            #print(self.kwargs.pop("source_interface"))
            si = self.kwargs.pop("source_interface")
            print(type(si))
            if isinstance(si, type(None)):
                pass
            elif isinstance(si, str):
                ref = ReferenceTo(pointer=f"interfaces.{si}")
                self.kwargs["source_interface"] = ref

            elif isinstance(si, Interface):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["source_interface"] = ref

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

class NetflowRecordIpv4Match(ConfigComponent):
    type = "NetflowRecordIpv4Match"
    model_cls = NetflowRecordIpv4MatchAttributes

    def pre_init(self):
        # Ensure that referenced components are added to the configuration before this component is added
        if self.kwargs.get("netflow_record") is not None:
            netflow_record = self.kwargs.pop("netflow_record")
            self.kwargs["netflow_record"] = netflow_record.name