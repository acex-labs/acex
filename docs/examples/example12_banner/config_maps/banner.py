from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import LoginBanner, MotdBanner

# Example of setting only Login banner
class SetLoginBanner(ConfigMap): 
    def compile(self, context):
        
        login_banner = LoginBanner(value="Welcome to the system!")
        context.configuration.add(login_banner)

# Example of setting only MOTD banner
class SetMotdBanner(ConfigMap):
    def compile(self, context):
        
        motd_banner = MotdBanner(value="""
****************************************
*              Essity LAB              *
*              Molndal HQ              *
*                                      *
*            SGNID: C1234567           *
****************************************
""")
        context.configuration.add(motd_banner)

## Example of setting both banners in one ConfigMap
#class SetBanners(ConfigMap):
#    def compile(self, context):
#        
#        login_banner = LoginBanner(value="Welcome to the system!")
#        motd_banner = MotdBanner(value="System maintenance at midnight.")
#        context.configuration.add(login_banner)
#        context.configuration.add(motd_banner)
#
login_banner = SetLoginBanner()
login_banner.filters = FilterAttribute("hostname").eq("/.*/")

motd_banner = SetMotdBanner()
motd_banner.filters = FilterAttribute("hostname").eq("/.*/")