from acex.configuration.components.base_component import ConfigComponent
#from acex.models.spanning_tree import SpanningTreeGlobalAttributes, SpanningTreeRSTPAttributes, SpanningTreeMSTPAttributes, SpanningTreeRapidPVSTAttributes
from acex.models.spanning_tree import SpanningTreeGlobalAttributes, RstpAttributes, MstpAttributes, MstpInstanceAttributes
#from acex.models.composed_configuration import ReferenceFrom, ReferenceTo

class SpanningTreeGlobal(ConfigComponent): 
    type = "SpanningTreeGlobal"
    model_cls = SpanningTreeGlobalAttributes
    # Interface logic here ?
    #def _add_interface(self):
    #    if self.kwargs.get('interface') is None:
    #        stp = self.kwargs.pop("stp_mode")
    #        self.kwargs["interface"] = ReferenceFrom(pointer=f"{stp.mode.name}.interfaces")

class SpanningTreeRSTP(ConfigComponent): 
    type = "SpanningTreeRSTP"
    model_cls = RstpAttributes

class SpanningTreeMSTP(ConfigComponent): 
    type = "SpanningTreeMSTP"
    model_cls = MstpAttributes

class SpanningTreeMstpInstance(ConfigComponent): 
    type = "SpanningTreeMstpInstance"
    model_cls = MstpInstanceAttributes
#
#class SpanningTreeRapidPVST(ConfigComponent): 
#    type = "SpanningTreeRapidPVST"
#    model_cls = SpanningTreeRapidPVSTAttributes

#    def pre_init(self):
#        # Handle vlan if any
#        if self.kwargs.get('vlan'):
#            vlan = self.kwargs.pop('vlan')
#            self.kwargs['vlan'] = vlan.vlan_id.value

#class SpanningTreeInterface(ConfigComponent):
#    type = "spanningTreeInterface"
#    model_cls = SpanningTreeInterfaceConfig