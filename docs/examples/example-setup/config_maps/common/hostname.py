from acex.configuration.components.system import HostName
from acex.config_map import ConfigMap, FilterAttribute


class SetHostname(ConfigMap):
    def compile(self, context):

        role_map = {
            "access": "asw",
            "distribution": "dsw",
            "core": "csw",
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
    FilterAttribute("role").eq("access")
    | FilterAttribute("role").eq("distribution")
    | FilterAttribute("role").eq("core")
)
