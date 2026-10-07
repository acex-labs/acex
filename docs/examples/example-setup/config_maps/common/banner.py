from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import LoginBanner, MotdBanner

class SetMotdBanner(ConfigMap):
    def compile(self, context):
        
        motd_banner = MotdBanner(value="""C
    #################################################################
    #                                                               #                                                              
    #  Authorized use only. This device is under monitoring and     #
    #  any attempt to login will be logged. Unauthorized use        #
    #  is prohibited and may be subject to criminal penalties.      #
    #                                                               #
    #  If you do not have authorization to use this device, log out #
    #  immediately!                                                 #
    #                                                               #                                                                
    #################################################################""")
        context.configuration.add(motd_banner)

motd_banner = SetMotdBanner()
motd_banner.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)