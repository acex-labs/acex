from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import Contact


class SetContact(ConfigMap): 
    def compile(self, context):
        
        C = Contact(value="""
        Andreas Andreasson
        Andreas.Andreasson@test.com
        Tel: +46708123456
        Mob: +46708123456"""
        )
        context.configuration.add(C)

contact = SetContact()
contact.filters = FilterAttribute("site").eq("/.*/")