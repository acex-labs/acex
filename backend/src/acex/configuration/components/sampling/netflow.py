from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import (
    NetflowCollectorAttributes,
    NetflowExporterAttributes,
    NetflowRecordAttributes,
    NetflowGlobalConfigAttributes,
    NetflowRecordIpv4Match as NetflowRecordIpv4MatchAttributes,
    NetflowRecordIpv4AddressMatch as NetflowRecordIpv4AddressMatchAttributes,
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

class NetflowRecord(ConfigComponent): 
    type = "NetflowRecord"
    model_cls = NetflowRecordAttributes
    def pre_init(self):
        print('='*100)
        print('NetflowRecord pre_init')
        print('self_kwargs: ')
        print(self.kwargs)
        print('='*100)
        #if self.kwargs.get("destination") is not None:
        #    self.kwargs["destination"] = ReferenceFrom(pointer=f"sampling.netflow.records.{self.kwargs['name'].name}.match_ipv4.destination")
        #if self.kwargs.get("source") is not None:
        #    self.kwargs["source"] = ReferenceFrom(pointer=f"sampling.netflow.records.{self.kwargs['name'].name}.match_ipv4.source")

class NetflowRecordIpv4Match(ConfigComponent):
    type = "NetflowRecordIpv4Match"
    model_cls = NetflowRecordIpv4MatchAttributes

    def pre_init(self):
        # Ensure that referenced components are added to the configuration before this component is added
            print('='*100)
            print('NetflowRecordIpv4Match pre_init')
            print('self_kwargs: ')
            print(self.kwargs)
            print('='*100)

class NetflowRecordIpv4AddressMatch(ConfigComponent):
    type = "NetflowRecordIpv4AddressMatch"
    model_cls = NetflowRecordIpv4AddressMatchAttributes

    def pre_init(self):
        print('='*100)
        print('NetflowRecordIpv4AddressMatch pre_init')
        print('self_kwargs: ')
        print(self.kwargs)
        print('='*100)
        if self.kwargs.get("netflow_record") is not None and self.kwargs.get("destination") == True:
                self.kwargs["netflow_record"] = ReferenceFrom(pointer=f"sampling.netflow.records.{self.kwargs['netflow_record'].name}.match_ipv4.destination")
        elif self.kwargs.get("netflow_record") is not None and self.kwargs.get("source") == True:
                self.kwargs["netflow_record"] = ReferenceFrom(pointer=f"sampling.netflow.records.{self.kwargs['netflow_record'].name}.match_ipv4.{self.kwargs['match_ipv4'].name}.source")
            #self.kwargs["netflow_record"] = ReferenceFrom(pointer=f"sampling.netflow.records.{self.kwargs['netflow_record'].name}.match_ipv4")