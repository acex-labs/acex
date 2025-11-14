
from acex.configuration.components import ConfigComponent
from acex.configuration.components.interfaces import (
    Interface,
    Loopback,
    Physical
)
from acex.configuration.components.system import SystemAttribute
from acex.configuration.components.system.logging_server import LoggingBase
from acex.configuration.components.system.ntp import NtpServer
from acex.configuration.components.system.ssh import SshServer
from acex.configuration.components.network_instances import NetworkInstance
from acex.models import ExternalValue
from collections import defaultdict
from typing import Dict


class Configuration:
    def __init__(self, logical_node_id):
        # TODO: Fixa struktur för hur config lagras/representeras

        # Components holds each config component unresolved until resolved by compiler
        # Does not set the representational model for config.
        self.components: Dict[str, ConfigComponent] = {}
        self.logical_node_id = logical_node_id

    def add(self, component: ConfigComponent):
        """
        Lagrar komponent i Configuration object, 
        använder path som nyckel. Varje komponent måste ha
        en hashbar path.
        """
        # For all external values, set reference!
        for k,v in component.attributes().items():
            if isinstance(v.data, ExternalValue):
                full_ref = f"logical_nodes.{self.logical_node_id}.{component.path}.{k}"
                v.data.ref = full_ref
                
        # Add to config object
        self.components[component.path] = component

    def _add_to_config_dict(self, component: ConfigComponent):
        """
        Adds the component to a correct path in the self.config.
        """
        if isinstance(component, Interface):
            self.config["interfaces"][component.type][component.path] = component

    def list_components(self):
        return list(self.components.values())


    def resolve(self, data_sources: dict):
        """
        Resolva alla DataSourceValue i alla komponenter med givna datakällor.
        """
        for component in self.components.values():
            if hasattr(component, "resolve_attributes"):
                component.resolve_attributes(data_sources)


    def to_json(self):
        """
        Serialisera alla komponenter till en dict (utan att resolva DataSourceValue).
        Nyckeln är component.path.
        """
        # Config holds the configuration representation:

        config = {

            "system": {
                "config": {
                    "contact": "",
                    "hostname": "",
                    "location": "",
                    "domain_name": "",
                },
                "aaa": {},
                "logging": {},
                "ntp": {},
                "ssh": {}
                },
            "acl": {},
            "vlans": {},
            "lldp": {},
            "interfaces": {},
            "network_instances": {}
        }

        for k, v in self.components.items():
            if isinstance(v, Interface):
                config["interfaces"][v.path] = v.to_json()
            elif isinstance(v, SystemAttribute):
                config["system"]["config"][v.type] = v.to_json()
            elif isinstance(v, LoggingBase):
                config["system"]["logging"][v.path] = v.to_json()
            elif isinstance(v, NtpServer):
                config["system"]["ntp"][v.path] = v.to_json()
            elif isinstance(v, SshServer):
                config["system"]["ssh"][v.path] = v.to_json()
            elif isinstance(v, NetworkInstance):
                config["network_instances"][v.path] = v.to_json()

        return config
