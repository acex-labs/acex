from acex.configuration.components.system import HostName
from acex.config_map import ConfigMap, FilterAttribute


class SetHostname(ConfigMap):
    def compile(self, context):

        role_map = {
            "lan_asw": "asw",
            "lan_distribution": "dsw",
            "lan_csw": "csw",
            "lan_ccore": "csw",
            "lan_core": "csw",
        }

        ln = context.logical_node

        sitename = ln.site
        site_id = sitename.removeprefix("C")
        last_six = site_id[-6:]
        function = role_map.get(ln.role, "X")

        # Nodes without a sequence fall back to their id
        sequence = ln.sequence if ln.sequence is not None else ln.id

        hostnameconf = HostName(value=f"{last_six}-{function}-{sequence:03}")

        context.configuration.add(hostnameconf)


config = SetHostname()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
