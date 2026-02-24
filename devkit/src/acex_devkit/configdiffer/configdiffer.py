from pydantic import BaseModel
from typing import Any, Dict, List, Iterator, Tuple

from acex_devkit.models.composed_configuration import ComposedConfiguration, Reference, ReferenceTo, ReferenceFrom, Metadata
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.configdiffer.diff import Diff, ComponentChange, AttributeChange, ComponentDiffOp

import json


class ConfigDiffer:

    IGNORED_KEYS = ["metadata", "logging", "ssh", "snmp", "network_instances", "interfaces", "ntp", "domain_name", "location", "contact", "motd_banner"]

    def _clean_metadata(self, obj: dict) -> dict:
        """
        Recursively ignored keys.
        """
        if not isinstance(obj, dict):
            return obj
        cleaned = {}
        for k, v in obj.items():
            if k in self.__class__.IGNORED_KEYS:
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


    def _flatten(self, d: dict, path: tuple = ()) -> Dict[tuple, dict]:
        """
        Recursively walk the tree and collect every component (dict with
        'component_class') into a flat mapping of path → component_dict.

        Example result:
            {
                ('interfaces', 'GigabitEthernet0/0/1'): {...},
                ('network_instances', 'default', 'vlans', '100'): {...},
            }
        """
        result = {}
        for key, value in d.items():
            current_path = path + (key,)
            if not isinstance(value, dict):
                continue
            # Try to find deeper components first
            deeper = self._flatten(value, current_path)
            if deeper:
                # Sub-components found — use those (don't emit current level)
                result.update(deeper)
            elif any(isinstance(v, dict) and 'value' in v for v in value.values()):
                # No sub-components, but this dict has AttributeValue fields → it's a leaf
                result[current_path] = value
        return result



    def _get_by_path(self, config: ComposedConfiguration, path: tuple) -> Any:
        """
        Traverse the ComposedConfiguration object using a path tuple and return
        the actual Pydantic model instance (or primitive) at that location.

        Example:
            path = ('interfaces', 'GigabitEthernet0/0/1')
            → returns the actual SoftwareLoopbackInterface / EthernetCsmacdInterface etc.
        """
        obj = config
        for key in path:
            if isinstance(obj, dict):
                obj = obj[key]
            else:
                obj = getattr(obj, key)
        return obj

    def _attribute_changes(self, before: dict, after: dict) -> List[AttributeChange]:
        """
        Compare two component dicts and return a list of changed attributes.
        """
        changes = []
        for key in set(before.keys()) | set(after.keys()):
            b = before.get(key)
            a = after.get(key)
            if b != a:
                changes.append(AttributeChange(attribute_name=key, before=b, after=a))
        return changes

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
        flat_observed = self._flatten(self._dump_to_dicts(observed_config))
        flat_desired = self._flatten(self._dump_to_dicts(desired_config))

        observed_paths = set(flat_observed.keys())
        desired_paths = set(flat_desired.keys())


        added = []
        removed = []
        changed = []

        for path in desired_paths - observed_paths:
            obj = self._get_by_path(desired_config, path)
            added.append(ComponentChange(
                op=ComponentDiffOp.ADD,
                path=list(path),
                component_type=type(obj),
                component_name=path[-1],
                before=None,
                after=obj,
                before_dict=None,
                after_dict=flat_desired[path],
            ))

        for path in observed_paths - desired_paths:
            obj = self._get_by_path(observed_config, path)
            removed.append(ComponentChange(
                op=ComponentDiffOp.REMOVE,
                path=list(path),
                component_type=type(obj),
                component_name=path[-1],
                before=obj,
                after=None,
                before_dict=flat_observed[path],
                after_dict=None,
            ))

        for path in desired_paths & observed_paths:
            desired_comp = flat_desired[path]
            observed_comp = flat_observed[path]
            if desired_comp != observed_comp:
                desired_obj = self._get_by_path(desired_config, path)
                observed_obj = self._get_by_path(observed_config, path)
                changed.append(ComponentChange(
                    op=ComponentDiffOp.CHANGE,
                    path=list(path),
                    component_type=type(desired_obj),
                    component_name=path[-1],
                    before=observed_obj,
                    after=desired_obj,
                    before_dict=observed_comp,
                    after_dict=desired_comp,
                    changed_attributes=self._attribute_changes(observed_comp, desired_comp),
                ))

        return Diff(added=added, removed=removed, changed=changed)

    