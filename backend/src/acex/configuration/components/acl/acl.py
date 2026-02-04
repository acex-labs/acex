from acex.configuration.components.base_component import ConfigComponent
from acex.models.acl_model import (
    Ipv4Acl as AclIpv4Attributes,
    Ipv6Acl as AclIpv6Attributes,
    Ipv4AclSet as Ipv4AclSetAttributes,
    Ipv6AclSet as Ipv6AclSetAttributes,
)

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