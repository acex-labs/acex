from pydantic import BaseModel
from typing import Any, Dict, List, Optional, get_origin, get_args

from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.configdiffer.diff import Diff, ComponentChange, AttributeChange, ComponentDiffOp


class ConfigDiffer:

    def _is_dict_of_models(self, annotation) -> bool:
        """Check if a type annotation is Dict[str, SomeBaseModel]."""
        origin = get_origin(annotation)
        if origin is dict:
            args = get_args(annotation)
            if len(args) == 2 and isinstance(args[1], type) and issubclass(args[1], BaseModel):
                return True
        return False

    def _is_base_model(self, annotation) -> bool:
        """Check if a type annotation is a BaseModel subclass (not Dict, not AttributeValue)."""
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
            # Optional[X] is Union[X, None]
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return non_none[0]
        return annotation

    def _flatten(self, model: BaseModel, path: tuple = ()) -> Dict[tuple, BaseModel]:
        """
        Recursively walk a Pydantic model using type annotations to find
        all components. Returns a flat mapping of path → model instance.

        Rules:
        - Dict[str, BaseModel] → component collection, each entry is a leaf
        - BaseModel (not in Dict) → container, recurse deeper
        - AttributeValue / primitives / None → skip (attributes, not components)
        """
        result = {}

        for field_name, field_info in model.model_fields.items():
            annotation = self._unwrap_optional(field_info.annotation)
            value = getattr(model, field_name)

            if value is None:
                continue

            if self._is_dict_of_models(annotation):
                # Component collection: each entry is a diffable component
                for key, component in value.items():
                    component_path = path + (field_name, key)
                    result[component_path] = component

            elif self._is_base_model(annotation):
                # Recurse deeper — if nothing found, this model itself is a leaf component
                child_path = path + (field_name,)
                deeper = self._flatten(value, child_path)
                if deeper:
                    result.update(deeper)
                else:
                    result[child_path] = value

        return result

    def _attribute_changes(self, before: BaseModel, after: BaseModel) -> List[AttributeChange]:
        """
        Compare two component model instances and return a list of changed attributes.
        """
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

        Uses Pydantic model introspection to find all components (entries in
        Dict[str, BaseModel] fields). Components are identified by their full
        path, e.g. ('interfaces', 'GigabitEthernet0/0/1').
        """
        flat_desired = self._flatten(desired_config)
        flat_observed = self._flatten(observed_config)

        desired_paths = set(flat_desired.keys())
        observed_paths = set(flat_observed.keys())

        added = []
        removed = []
        changed = []

        for path in desired_paths - observed_paths:
            obj = flat_desired[path]
            added.append(ComponentChange(
                op=ComponentDiffOp.ADD,
                path=list(path),
                component_type=type(obj),
                component_name=path[-1],
                before=None,
                after=obj,
                before_dict=None,
                after_dict=obj.model_dump(),
            ))

        for path in observed_paths - desired_paths:
            obj = flat_observed[path]
            removed.append(ComponentChange(
                op=ComponentDiffOp.REMOVE,
                path=list(path),
                component_type=type(obj),
                component_name=path[-1],
                before=obj,
                after=None,
                before_dict=obj.model_dump(),
                after_dict=None,
            ))

        for path in desired_paths & observed_paths:
            desired_obj = flat_desired[path]
            observed_obj = flat_observed[path]
            if desired_obj != observed_obj:
                changed.append(ComponentChange(
                    op=ComponentDiffOp.CHANGE,
                    path=list(path),
                    component_type=type(desired_obj),
                    component_name=path[-1],
                    before=observed_obj,
                    after=desired_obj,
                    before_dict=observed_obj.model_dump(),
                    after_dict=desired_obj.model_dump(),
                    changed_attributes=self._attribute_changes(observed_obj, desired_obj),
                ))

        return Diff(
            added=added,
            removed=removed,
            changed=changed,
            total_desired=len(desired_paths),
            total_observed=len(observed_paths),
        )
