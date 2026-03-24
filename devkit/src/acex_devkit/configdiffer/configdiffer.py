from collections import defaultdict
from pydantic import BaseModel
from typing import Any, Dict, List, Tuple, Optional, get_origin, get_args, Union

from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.container_model import ContainerModel
from acex_devkit.configdiffer.diff import Diff, ComponentChange, AttributeChange, ComponentDiffOp


class ConfigDiffer:

    def _is_container(self, annotation) -> bool:
        """Check if a type annotation is a plain BaseModel subclass (not ContainerModel, not AttributeValue)."""
        return (
            isinstance(annotation, type)
            and issubclass(annotation, BaseModel)
            and not issubclass(annotation, AttributeValue)
        )

    def _unwrap_optional(self, annotation):
        """Unwrap Optional[X] to X. Returns the annotation unchanged if not Optional."""
        origin = get_origin(annotation)
        if origin is type(None):
            return annotation
        args = get_args(annotation)
        if args:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return non_none[0]
        return annotation

    def _is_leaf(self, model: BaseModel) -> bool:
        """A model is a leaf if it has at least one direct AttributeValue field."""
        for field_info in model.model_fields.values():
            if get_origin(field_info.annotation) is AttributeValue:
                return True
            args = get_args(field_info.annotation)
            if any(get_origin(a) is AttributeValue for a in args):
                return True
        return False

    def _flatten(self, model: BaseModel, path: tuple = ()) -> Dict[tuple, BaseModel]:
        """
        Recursively walk a model tree, collecting leaf nodes.
        A leaf is any BaseModel that has direct AttributeValue fields.
        Returns a flat mapping of path → leaf instance.
        """
        result = {}

        for field_name in model.model_fields:
            value = getattr(model, field_name, None)
            if value is None or isinstance(value, AttributeValue):
                continue

            field_path = path + (field_name,)

            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(item, BaseModel):
                        continue
                    item_path = field_path + (key,)
                    if self._is_leaf(item):
                        result[item_path] = item
                    else:
                        result.update(self._flatten(item, item_path))

            elif isinstance(value, BaseModel):
                if self._is_leaf(value):
                    result[field_path] = value
                else:
                    result.update(self._flatten(value, field_path))

        return result


    def _attribute_changes(self, before: BaseModel, after: BaseModel) -> List[AttributeChange]:
        """Compare two component instances and return a list of changed attributes."""
        changes = []
        all_fields = set(before.model_fields.keys()) | set(after.model_fields.keys())
        for field_name in all_fields:
            b = getattr(before, field_name, None)
            a = getattr(after, field_name, None)
            if b != a:
                changes.append(AttributeChange(attribute_name=field_name, before=b, after=a))
        return changes

    def diff(self, *, desired_config: ComposedConfiguration, observed_config: ComposedConfiguration) -> Diff:
        """
        Compare two ComposedConfiguration objects and return a component-based diff.

        Components are matched by their identity_fields (field values), not by dict key.
        This handles cases where the parser produces different key formats for the same
        physical component (e.g. "Gi0/0/1" vs "GigabitEthernet0/0/1").

        Components with identity_fields = () fall back to key-based matching.
        """
        flat_desired = self._flatten(desired_config)
        print(flat_desired)

        exit()
        flat_observed = self._flatten(observed_config)

        # Group components by their container path (parent path = all but last element)
        # so that identity matching is scoped to the same container.
        desired_by_container: Dict[tuple, Dict[str, Any]] = defaultdict(dict)
        observed_by_container: Dict[tuple, Dict[str, Any]] = defaultdict(dict)

        for path, component in flat_desired.items():
            desired_by_container[path[:-1]][path[-1]] = component

        for path, component in flat_observed.items():
            observed_by_container[path[:-1]][path[-1]] = component

        added = []
        removed = []
        changed = []

        all_container_paths = set(desired_by_container) | set(observed_by_container)

        for container_path in all_container_paths:
            d_components = desired_by_container.get(container_path, {})
            o_components = observed_by_container.get(container_path, {})

            matched, unmatched_d, unmatched_o = self._match_by_identity(d_components, o_components)

            for d_key, _o_key, d_obj, o_obj in matched:
                if d_obj != o_obj:
                    path = list(container_path) + [d_key]
                    changed.append(ComponentChange(
                        op=ComponentDiffOp.CHANGE,
                        path=path,
                        component_type=type(d_obj),
                        component_name=d_key,
                        before=o_obj,
                        after=d_obj,
                        before_dict=o_obj.model_dump(),
                        after_dict=d_obj.model_dump(),
                        changed_attributes=self._attribute_changes(o_obj, d_obj),
                    ))

            for d_key, d_obj in unmatched_d.items():
                path = list(container_path) + [d_key]
                added.append(ComponentChange(
                    op=ComponentDiffOp.ADD,
                    path=path,
                    component_type=type(d_obj),
                    component_name=d_key,
                    before=None,
                    after=d_obj,
                    before_dict=None,
                    after_dict=d_obj.model_dump(),
                ))

            for o_key, o_obj in unmatched_o.items():
                path = list(container_path) + [o_key]
                removed.append(ComponentChange(
                    op=ComponentDiffOp.REMOVE,
                    path=path,
                    component_type=type(o_obj),
                    component_name=o_key,
                    before=o_obj,
                    after=None,
                    before_dict=o_obj.model_dump(),
                    after_dict=None,
                ))

        return Diff(
            added=added,
            removed=removed,
            changed=changed,
            total_desired=len(flat_desired),
            total_observed=len(flat_observed),
        )
