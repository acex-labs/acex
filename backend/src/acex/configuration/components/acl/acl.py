from acex.configuration.components.base_component import ConfigComponent
from acex.models.acl_model import (
    #AclEntryAttributes,
    Ipv4Acl as AclIpv4Attributes,
    Ipv6Acl as AclIpv6Attributes,
    Ipv4AclSet as Ipv4AclSetAttributes,
    Ipv6AclSet as Ipv6AclSetAttributes,
    #AclIcmpv4Attributes,
    #AclTransportAttributes
)

#class AclEntry(ConfigComponent):
#    """
#    ACL Configuration Component
#    """
#    type = "AclEntry"
#    model_cls = AclEntryAttributes
#
#    def pre_init(self):
#        if 'ipv4' in self.kwargs:
#            ipv4 = self.kwargs.pop('ipv4')
#
#            if isinstance(ipv4, type(None)):
#                pass
#
#            if isinstance(ipv4, AclIpv4):
#                ref = ipv4.get_reference()
#                self.kwargs['ipv4'] = ref

class Ipv4AclSet(ConfigComponent):
    """
    ACL IPv4 Set Configuration Component
    """
    type = "ipv4acl_set"
    model_cls = Ipv4AclSetAttributes

class Ipv6AclSet(ConfigComponent):
    """
    ACL IPv6 Set Configuration Component
    """
    type = "ipv6acl_set"
    model_cls = Ipv6AclSetAttributes

class AclIpv4(ConfigComponent):
    """
    ACL IPv4 Configuration Component
    """
    type = "ipv4acl"
    model_cls = AclIpv4Attributes

    def pre_init(self):
        if 'ipv4acl_set' in self.kwargs:
            acl_set = self.kwargs.pop('ipv4acl_set')
            self.kwargs['ipv4acl_set'] = acl_set.name

class AclIpv6(ConfigComponent):
    """
    ACL IPv6 Configuration Component
    """
    type = "ipv6acl"
    model_cls = AclIpv6Attributes

    def pre_init(self):
        if 'ipv6acl_set' in self.kwargs:
            acl_set = self.kwargs.pop('ipv6acl_set')
            self.kwargs['ipv6acl_set'] = acl_set.name

#class AclIcmpv4(ConfigComponent):
#    """
#    ACL ICMPv4 Configuration Component
#    """
#    type = "AclIcmpv4"
#    model_cls = AclIcmpv4Attributes#

#class AclTransport(ConfigComponent):
#    """
#    ACL Transport Configuration Component
#    """
#    type = "AclTransport"
#    model_cls = AclTransportAttributes