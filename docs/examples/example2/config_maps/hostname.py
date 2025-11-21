
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import HostName, DomainName


class SetHostname(ConfigMap): 
    def compile(self, context):
        ln = context.logical_node
        Hn = HostName(value=f"{ln.site}-{ln.role}-{ln.sequence:02d}")
        # Hn = HostName(value=context.integrations.ipam.data.ip_addresses({}))
        context.configuration.add(Hn)


        Dn = DomainName(value=f"{context.configuration.hostname}.domain.com")
        context.configuration.add(Dn)

hostname = SetHostname()
hostname_filter = FilterAttribute("hostname").eq("/.*/")
hostname.filters = hostname_filter
