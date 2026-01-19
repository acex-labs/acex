from acex.configuration.components.base_component import ConfigComponent
from acex.models.spanning_tree import SpanningTreeGlobalAttributes, SpanningTreeRSTPAttributes, SpanningTreeMSTPAttributes, SpanningTreeRapidPVSTAttributes
from acex.models.composed_configuration import ReferenceFrom, ReferenceTo

class SpanningTreeGlobal(ConfigComponent): 
    type = "SpanningTreeGlobal"
    model_cls = SpanningTreeGlobalAttributes
    # Interface logic here ?
    #def _add_interface(self):
    #    if self.kwargs.get('interface') is None:
    #        stp = self.kwargs.pop("stp_mode")
    #        self.kwargs["interface"] = ReferenceFrom(pointer=f"{stp.mode.name}.interfaces")

class SpanningTreeRSTP(ConfigComponent): 
    type = "spanningTreeRSTP"
    model_cls = SpanningTreeRSTPAttributes

class SpanningTreeMSTP(ConfigComponent): 
    type = "spanningTreeMSTP"
    model_cls = SpanningTreeMSTPAttributes

class SpanningTreeRapidPVST(ConfigComponent): 
    type = "spanningTreeRapidPVST"
    model_cls = SpanningTreeRapidPVSTAttributes

#class SpanningTreeInterface(ConfigComponent):
#    type = "spanningTreeInterface"
#    model_cls = SpanningTreeInterfaceConfig