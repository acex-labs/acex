from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.acl import (
    #AclEntry,
    #AclIpv4, 
    #AclIcmpv4,
    #AclTransport
    AclIpv4,
    AclIpv6
)

class AclConfig(ConfigMap):
    #def compile(self, context):
    #    ipv4acl = AclEntry(
    #        name = 'ipv4_acl', 
    #        source_ipv4 = 'any',
    #        destination_ipv4 = 'any'
    #    )
    #    context.configuration.add(ipv4acl)
#
    #    #transportacl = AclEntry(
    #    #    name = 'transport_acl', 
    #    #    protocol = 1 # ICMP
    #    #)
    #    #context.configuration.add(transportacl)
#
    #    acl_entry = AclEntry(
    #        name = 'permit_icmp', 
    #        sequence_id = 10,
    #        description = 'Permit ICMP traffic',
    #        ipv4 = ipv4acl, #reference
    #        #transport = transportacl #reference
    #    )
    #    context.configuration.add(acl_entry)

    def compile(self, context):
        ipv4aclentry = AclIpv4(
            name = 'ipv4aclentry',
            sequence_id = 10,
            description = 'Permit Ipv4 traffic',
            source = '172.16.1.0/24',
            destination = '192.168.1.0/24',
            #protocol = 'TCP'
        )

        context.configuration.add(ipv4aclentry)

        ipv6aclentry = AclIpv6(
            name = 'ipv6aclentry',
            sequence_id = 10,
            description = 'Permit Ipv6 traffic',
            source = '2001:db8:1::/64',
            destination = '2001:db8:2::/64',
            #protocol = 'TCP'
        )

        context.configuration.add(ipv6aclentry)


acl_config = AclConfig()
acl_config.filters = FilterAttribute("site").eq("/.*/")