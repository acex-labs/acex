from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import (
    NetflowCollectorAttributes,
    NetflowExporterAttributes,
    NetflowRecordAttributes
)

class NetflowCollector(ConfigComponent): 
    type = "NetflowCollector"
    model_cls = NetflowCollectorAttributes

class NetflowExporter(ConfigComponent): 
    type = "NetflowExporter"
    model_cls = NetflowExporterAttributes

class NetflowRecord(ConfigComponent): 
    type = "NetflowRecord"
    model_cls = NetflowRecordAttributes