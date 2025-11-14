
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import DomainName


class SetDN(ConfigMap): 
    def compile(self, context):
        
        Dn = DomainName(f"{context.logical_node.hostname}.ngninfra.net")
        context.configuration.add(Dn)

# hostname = SetDN()
# hostname_filter = FilterAttribute("hostname").eq("/.*/")
# hostname.filters = hostname_filter
