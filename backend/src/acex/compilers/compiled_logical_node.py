from typing import Callable, Union, Awaitable
from acex.config_map import ConfigMap, ConfigMapContext
import inspect
from acex.models import LogicalNodeResponse
from acex.configuration import Configuration
import traceback
import sys



class CompiledLogicalNode: 

    def __init__(self, configuration: Configuration, logical_node: dict, integrations):
        self.logical_node = logical_node
        self.configuration = configuration
        self.context = ConfigMapContext(logical_node, configuration, integrations)
        self.meta_data = {} # Får inte heta "metadata" pga SQLModel
        self.processors = []
        self.completed_processors = []
        self.errors = []
        self.integrations = integrations

    @property
    def response(self):
        response = self.logical_node.model_dump()
        compiled = self.processors == self.completed_processors
        response["meta_data"] = {"compiled": compiled}
        response["meta_data"]["registered_processors"] = [str(x.__self__.__class__) for x in self.processors]
        response["meta_data"]["completed_processors"] = [str(x.__self__.__class__) for x in self.completed_processors]
        response["meta_data"]["errors"] = self.errors
        response["configuration"] = self.configuration.to_json()
        return LogicalNodeResponse(**response)

    def check_config_map_filter(self, config_map: ConfigMap):
        """
        Returns True if the config_map matches the logical node's filter.
        This method should be implemented to check against the logical node's filters.
        """
        if config_map.filters is not None:
            for exp in config_map.filters.as_alternatives():
                match = exp.match(self.logical_node)
                if match is True:
                    return True
        return False

    async def run_processor(self, processor):
        if inspect.iscoroutinefunction(processor):
            await processor(self.context)
        else:
            processor(self.context)


    async def compile(self):
        # run all registered processors
        for processor in self.processors:

            # Try each registered processor.
            try:
                await self.run_processor(processor)
                self.completed_processors.append(processor)
            except Exception as e:
                exc_type, exc_value, exc_tb = sys.exc_info()
                tb_list = traceback.format_tb(exc_tb)
                filtered_tb = tb_list[2:]
                tb_str = "".join(filtered_tb)

                self.errors.append({"processor": str(processor), "error": str(e), "traceback": tb_str})
                print(f"Error in processor {processor}: {e}")
                print(tb_str)
                continue



    def register(self, fn: Callable[[dict], Union[dict, Awaitable[dict]]]):
        """Register a new compile processor."""
        self.processors.append(fn)
