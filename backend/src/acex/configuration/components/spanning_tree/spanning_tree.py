from acex.configuration.components.base_component import ConfigComponent
from acex.models.spanning_tree import SpanningTreeGlobal as SpanningTreeGlobalAttributes, SpanningTreeRSTP, SpanningTreeMSTP, SpanningTreeRapidPVST, SpanningTreeInterfaceConfig
from acex.models.composed_configuration import ReferenceFrom, ReferenceTo

class SpanningTreeGlobal(ConfigComponent): 
    type = "spanningTree"
    model_cls = SpanningTreeGlobalAttributes
    # Interface logic here

    def _add_interface(self):
        if self.kwargs.get('interface') is None:
            stp = self.kwargs.pop("stp_mode")
            self.kwargs["interface"] = ReferenceFrom(pointer=f"{stp.mode.name}.interfaces")

class SpanningTreeRSTPComponent(ConfigComponent): 
    type = "spanningTreeRSTP"
    model_cls = SpanningTreeRSTP

class SpanningTreeMSTPComponent(ConfigComponent): 
    type = "spanningTreeMSTP"
    model_cls = SpanningTreeMSTP

class SpanningTreeRapidPVSTComponent(ConfigComponent): 
    type = "spanningTreeRapidPVST"
    model_cls = SpanningTreeRapidPVST

class SpanningTreeInterface(ConfigComponent):
    type = "spanningTreeInterface"
    model_cls = SpanningTreeInterfaceConfig