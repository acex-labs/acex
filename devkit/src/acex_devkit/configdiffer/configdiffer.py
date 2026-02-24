from pydantic import BaseModel
from typing import Any, Dict, List, Iterator, Tuple

from acex_devkit.models.composed_configuration import ComposedConfiguration, Reference, ReferenceTo, ReferenceFrom, Metadata
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.configdiffer.diff import Diff, ComponentChange, AttributeChange, ComponentDiffOp

import json


class ConfigDiffer:

    IGNORED_KEYS = ["metadata"]

    def _clean_metadata(self, obj: dict) -> dict:
        """
        Recursively ignored keys.
        """
        if not isinstance(obj, dict):
            return obj
        
        cleaned = {}
        for k, v in obj.items():
            if k == "metadata":
                # Keep only component_class from metadata
                if isinstance(v, dict) and "component_class" in v:
                    cleaned["component_class"] = v["component_class"]
                continue
            
            if isinstance(v, dict):
                cleaned[k] = self._clean_metadata(v)
            elif isinstance(v, list):
                cleaned[k] = [self._clean_metadata(item) if isinstance(item, dict) else item for item in v]
            else:
                cleaned[k] = v
        
        return cleaned


    def _dump_to_dicts(self, config: ComposedConfiguration) -> dict:
        """
        Dumps to dict, removes unnecessary keys except component_class. 
        """
        # Remove most metadata, but keep component_class for type identification
        config_dict = config.model_dump(exclude_unset=True)
        return self._clean_metadata(config_dict)
    

    def diff(self, *, desired_config: ComposedConfiguration, observed_config: ComposedConfiguration) -> Diff:
        """
        Compare two ComposedConfiguration objects and return a component-based diff.

        Walks both configs using Pydantic model structure (not heuristics) to find
        all named components inside Dict[str, Model] containers. Components are
        identified by their full path, e.g. ('interfaces', 'GigabitEthernet0/0/1').

        Args:
            desired_config: The target configuration we want to achieve.
            observed_config: The current configuration as observed on the device.

        Returns:
            Diff: A structured diff showing added, removed, and changed components.
        """

        observed_dict = self._dump_to_dicts(observed_config)
        desired_dict = self._dump_to_dicts(desired_config)

        # print(json.dumps(observed_dict["system"]["config"]["hostname"], indent=4))
        # print(json.dumps(desired_dict["system"]["config"]["hostname"], indent=4))

        print(json.dumps(desired_dict, indent=4))





    