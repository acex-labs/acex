from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import Contact


class SetContact(ConfigMap):
    def compile(self, context):
        contact = Contact(value="user1@example.com")
        context.configuration.add(contact)


config = SetContact()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
