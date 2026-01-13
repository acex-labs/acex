
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import HostName


class SetHostname(ConfigMap): 
    def compile(self, context):
        
        Hn = HostName(value=context.logical_node.hostname)
        context.configuration.add(Hn)

hostname = SetHostname()
hostname.filters = FilterAttribute("hostname").eq("/.*/")
