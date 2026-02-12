from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.spanning_tree import SpanningTreeGlobalAttributes, RstpAttributes, MstpAttributes, MstpInstanceAttributes, RapidPVSTAttributes

class SpanningTreeGlobal(ConfigComponent): 
    type = "SpanningTreeGlobal"
    model_cls = SpanningTreeGlobalAttributes

class SpanningTreeRSTP(ConfigComponent): 
    type = "SpanningTreeRSTP"
    model_cls = RstpAttributes

class SpanningTreeMSTP(ConfigComponent): 
    type = "SpanningTreeMSTP"
    model_cls = MstpAttributes

class SpanningTreeMstpInstance(ConfigComponent): 
    type = "SpanningTreeMstpInstance"
    model_cls = MstpInstanceAttributes

class SpanningTreeRapidPVST(ConfigComponent): 
    type = "SpanningTreeRapidPVST"
    model_cls = RapidPVSTAttributes