from collections import defaultdict
from pydantic import BaseModel
from typing import Any, Dict, List, Tuple, Optional, get_origin, get_args, Union

from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.container_model import ContainerModel
from acex_devkit.configdiffer.diff import Diff, ComponentChange, AttributeChange, ComponentDiffOp


class ConfigDiffer:

    def _is_dict_of_containers(self, annotation) -> bool:
        """Check if a type annotation is Dict[str, ContainerModel] or Dict[str, Union[ContainerModel, ...]]."""
        if get_origin(annotation) is not dict:
            return False
        args = get_args(annotation)
        if len(args) != 2:
            return False
        val_type = args[1]

        # Dict[str, SomeContainerModel]
        if isinstance(val_type, type) and issubclass(val_type, ContainerModel):
            return True

        # Dict[str, Union[ContainerA, ContainerB, ...]]  (e.g. interfaces field)
        if get_origin(val_type) is Union:
            union_args = [a for a in get_args(val_type) if a is not type(None)]
            return bool(union_args) and all(
                isinstance(a, type) and issubclass(a, ContainerModel)
                for a in union_args
            )

        return False

    def _is_base_model(self, annotation) -> bool:
        """Check if a type annotation is a plain BaseModel subclass (not ContainerModel, not AttributeValue)."""
        return (
            isinstance(annotation, type)
            and issubclass(annotation, BaseModel)
            and not issubclass(annotation, ContainerModel)
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

    def _flatten(self, model: BaseModel, path: tuple = ()) -> Dict[tuple, BaseModel]:
        """
        Recursively walk a Pydantic model to find all container components.
        Returns a flat mapping of path → component instance.

        Rules:
        - Dict[str, ContainerModel] (or Union variant) → container collection,
          each entry becomes a leaf at path (field_name, key)
        - Plain BaseModel (not ContainerModel, not AttributeValue) → structural
          container, recurse deeper
        - AttributeValue / primitives / None → skip
        """
        result = {}

        for field_name, field_info in model.model_fields.items():
            annotation = self._unwrap_optional(field_info.annotation)
            value = getattr(model, field_name)

            if value is None:
                continue

            if self._is_dict_of_containers(annotation):
                for key, component in value.items():
                    result[path + (field_name, key)] = component

            elif self._is_base_model(annotation):
                child_path = path + (field_name,)
                deeper = self._flatten(value, child_path)
                if deeper:
                    result.update(deeper)
                else:
                    result[child_path] = value

        return result

    def _identity_key(self, component: ContainerModel) -> Optional[tuple]:
        """
        Extract the identity tuple from a component's identity_fields.
        Returns None if identity_fields is empty (key-based matching).
        Unwraps AttributeValue wrappers to compare raw values.
        """
        fields = type(component).identity_fields
        if not fields:
            return None
        values = []
        for field_name in fields:
            v = getattr(component, field_name, None)
            if isinstance(v, AttributeValue):
                v = v.value
            values.append(v)
        return tuple(values)

    def _match_by_identity(
        self,
        desired: Dict[str, ContainerModel],
        observed: Dict[str, ContainerModel],
    ) -> Tuple[List[Tuple[str, str, Any, Any]], Dict[str, Any], Dict[str, Any]]:
        """
        Match desired and observed components by identity_fields values.

        For components with non-empty identity_fields: match pairs that share the
        same identity values regardless of dict key.
        For components with empty identity_fields: match by dict key (current behaviour).

        Returns:
            matched      — list of (desired_key, observed_key, desired_obj, observed_obj)
            unmatched_d  — desired components with no observed counterpart → ADD
            unmatched_o  — observed components with no desired counterpart → REMOVE
        """
        if not desired and not observed:
            return [], {}, {}

        # Determine matching strategy from a sample component
        sample = next(iter(desired.values()), next(iter(observed.values()), None))
        use_key_matching = sample is None or not type(sample).identity_fields

        if use_key_matching:
            # Key-based: identical to original behaviour
            matched = []
            unmatched_d = {}
            unmatched_o = {}
            d_keys = set(desired)
            o_keys = set(observed)
            for key in d_keys & o_keys:
                matched.append((key, key, desired[key], observed[key]))
            for key in d_keys - o_keys:
                unmatched_d[key] = desired[key]
            for key in o_keys - d_keys:
                unmatched_o[key] = observed[key]
            return matched, unmatched_d, unmatched_o

        # Identity-based matching
        remaining_d = dict(desired)
        remaining_o = dict(observed)
        matched = []

        # Build a lookup: identity_key → (dict_key, component) for observed
        o_by_identity: Dict[tuple, Tuple[str, Any]] = {}
        for o_key, o_obj in remaining_o.items():
            ik = self._identity_key(o_obj)
            if ik is not None:
                o_by_identity[ik] = (o_key, o_obj)

        for d_key, d_obj in list(remaining_d.items()):
            ik = self._identity_key(d_obj)
            if ik is not None and ik in o_by_identity:
                o_key, o_obj = o_by_identity.pop(ik)
                matched.append((d_key, o_key, d_obj, o_obj))
                del remaining_d[d_key]
                del remaining_o[o_key]

        return matched, remaining_d, remaining_o

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
