
from acex.plugins.neds.core import RendererBase
from typing import Any, Dict, Optional
from pathlib import Path

from jinja2 import Environment, FileSystemLoader



class JunosCLIRenderer(RendererBase):

    def _load_template_file(self) -> str:
        """Load a Jinja2 template file."""
        template_name = "template.j2"
        path = Path(__file__).parent
        env = Environment(loader=FileSystemLoader(path))
        template = env.get_template(template_name)
        return template

    def render(self, logical_node: Dict[str, Any], asset) -> Any:
        """Render the configuration model for Junos CLI devices."""
        configuration = logical_node.configuration
        processed_config = self.pre_process(configuration, asset)
        template = self._load_template_file()
        return template.render(configuration=processed_config)

    def pre_process(self, configuration, asset) -> Dict[str, Any]:
        """Pre-process the configuration model before rendering j2."""
        configuration = self.physical_interface_names(configuration, asset)
        return configuration


    def physical_interface_names(self, configuration, asset) -> None:
        """Assign physical interface names based on asset data."""

        for _,intf in configuration.get("interfaces", {}).items():
            if intf["type"] == "ethernetCsmacd":
                index = intf["config"]["index"]["value"]
                speed = intf["config"]["speed"]["value"]
                intf_prefix = self.get_port_prefix(speed)
                intf_suffix = self.get_port_suffix(asset.hardware_model, index)
                intf["config"]["name"] = f"{intf_prefix}{intf_suffix}"

        return configuration

    def get_port_prefix(self, speed:int) -> Optional[str]:
        PREFIX_MAP = {
            1000000: "ge",
            1000000000: "xe"
        }
        return PREFIX_MAP.get(speed) or "UnknownIfPrefix"


    def get_port_suffix(self, hardware_model:str, index:int) -> Optional[str]:
        max_index = 0
        suffix_string = ""

        suffix_string = f"-0/0/{index+1}"
        return suffix_string