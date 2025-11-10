
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.aaa import (
    aaaBase,
    aaaAuthorizaion,
    aaaAuthentication,
    aaaAccounting
)


class SetAaaBase(ConfigMap): 
    def compile(self, context):
        
        aaaBaseConfig = aaaBase(
            name='aaa_config',
            enable=True,
            tacacs_servers=['192.168.1.1','172.16.1.1'],
            tacacs_all={
                'name':'tacacs-vip',
                'timeout':30,
                'port':49
            } # group for all tacacs servers
        )
        context.configuration.add(aaaBaseConfig)

class SetAaaAuthentication(ConfigMap):
    def compile(self, context):

        aaaAuthenticationConfig = aaaAuthentication(
            console=True,
            config_commands=True
        )

        context.configuration.add(aaaAuthenticationConfig)

class SetAaaAuthorizaion(ConfigMap):
    def compile(self, context):

        aaaAuthorizaionConfig = aaaAuthorizaion(
            console=True,
            config_commands=True
        )

        context.configuration.add(aaaAuthorizaionConfig)

class SetAaaAccounting(ConfigMap):
    def compile(self, context):

        aaaAccConfig = aaaAccounting(
            console=True,
            config_commands=True
        )

        context.configuration.add(aaaAccConfig)

aaa_base = SetAaaBase()
aaa_base_filter = FilterAttribute("hostname").eq("/.*/")
aaa_base.filters = aaa_base_filter