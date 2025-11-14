
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import Contact



class SetContact(ConfigMap): 
    def compile(self, context):
        
        C = Contact("KK")
        context.configuration.add(C)



contact = SetContact()
cfilter = FilterAttribute("hostname").eq("/.*/")
contact.filters = cfilter
