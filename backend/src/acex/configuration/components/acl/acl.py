from acex.configuration.components.base_component import ConfigComponent
from acex.models.acl_model import (
    AclEntryAttributes,
    Ipv4Acl as AclIpv4Attributes,
    Ipv6Acl as AclIpv6Attributes,
    AclIcmpv4Attributes,
    AclTransportAttributes
)

class AclEntry(ConfigComponent):
    """
    ACL Configuration Component
    """
    type = "AclEntry"
    model_cls = AclEntryAttributes

    def pre_init(self):
        if 'ipv4' in self.kwargs:
            ipv4 = self.kwargs.pop('ipv4')

            if isinstance(ipv4, type(None)):
                pass

            if isinstance(ipv4, AclIpv4):
                ref = ipv4.get_reference()
                self.kwargs['ipv4'] = ref

class AclIpv4(ConfigComponent):
    """
    ACL IPv4 Configuration Component
    """
    type = "AclIpv4"
    model_cls = AclIpv4Attributes

class AclIpv6(ConfigComponent):
    """
    ACL IPv6 Configuration Component
    """
    type = "AclIpv6"
    model_cls = AclIpv6Attributes

class AclIcmpv4(ConfigComponent):
    """
    ACL ICMPv4 Configuration Component
    """
    type = "AclIcmpv4"
    model_cls = AclIcmpv4Attributes

class AclTransport(ConfigComponent):
    """
    ACL Transport Configuration Component
    """
    type = "AclTransport"
    model_cls = AclTransportAttributes