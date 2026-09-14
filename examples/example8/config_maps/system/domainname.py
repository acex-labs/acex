
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import DomainName


class SetDN(ConfigMap): 
    def compile(self, context):
        
        Dn = DomainName(value=f"example.com")
        context.configuration.add(Dn)

hostname = SetDN()
hostname.filters = FilterAttribute("hostname").eq("/.*/")
