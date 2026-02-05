from acex.configuration.components.base_component import ConfigComponent
from acex.models.acl_model import (
    Ipv4AclEntryAttributes,
    Ipv6AclEntryAttributes,
    Ipv4AclAttributes,
    Ipv6AclAttributes,
)

class Ipv4Acl(ConfigComponent):
    """
    ACL IPv4 Set Configuration Component
    """
    type = "ipv4_acl"
    model_cls = Ipv4AclAttributes

class Ipv6Acl(ConfigComponent):
    """
    ACL IPv6 Set Configuration Component
    """
    type = "ipv6_acl"
    model_cls = Ipv6AclAttributes

class Ipv4AclEntry(ConfigComponent):
    """
    ACL IPv4 Configuration Component
    """
    type = "ipv4_acl_entry"
    model_cls = Ipv4AclEntryAttributes

    def pre_init(self):
        if 'ipv4_acl' in self.kwargs:
            acl_set = self.kwargs.pop('ipv4_acl')
            self.kwargs['ipv4_acl'] = acl_set.name

class Ipv6AclEntry(ConfigComponent):
    """
    ACL IPv6 Configuration Component
    """
    type = "ipv6_acl_entry"
    model_cls = Ipv6AclEntryAttributes

    def pre_init(self):
        if 'ipv6_acl' in self.kwargs:
            acl_set = self.kwargs.pop('ipv6_acl')
            self.kwargs['ipv6_acl'] = acl_set.name