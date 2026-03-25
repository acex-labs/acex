from collections import defaultdict
from pydantic import BaseModel
from typing import Any, Dict, List, get_args

from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.container_entry import ContainerEntry
from acex_devkit.configdiffer.diff import Diff, ComponentChange, AttributeChange, ComponentDiffOp


class ConfigDiffer:

    def _is_leaf(self, model: BaseModel) -> bool:
        """A model is a leaf if it has at least one direct AttributeValue field."""
        for field_info in model.model_fields.values():
            ann = field_info.annotation
            if isinstance(ann, type) and issubclass(ann, AttributeValue):
                return True
            for arg in get_args(ann):
                if isinstance(arg, type) and issubclass(arg, AttributeValue):
                    return True
        return False

    def _flatten(self, model: BaseModel, path: tuple = ()) -> Dict[tuple, BaseModel]:
        """
        Recursively walk a model tree, collecting leaf nodes.
        A leaf is any BaseModel that has direct AttributeValue fields.
        A model can be both a leaf (stored) and have children (recursed into).
        Returns a flat mapping of path → leaf instance.
        """
        result = {}

        # Store this model if it has AttributeValue fields (e.g. SystemConfig, NtpServer, NetworkInstance)
        if self._is_leaf(model):
            result[path] = model

        # Walk each field declared on the model (e.g. System has config, aaa, logging, ntp, ssh, snmp)
        for field_name in model.model_fields:
            value = getattr(model, field_name, None)
            if value is None:
                continue

            # Skip data fields — AttributeValue holds actual config values (e.g. hostname, enabled)
            if isinstance(value, AttributeValue):
                continue

            # Single nested model — recurse deeper (e.g. System.config → SystemConfig, System.ssh → Ssh)
            if isinstance(value, BaseModel):
                result.update(self._flatten(value, path + (field_name,)))

            # Keyed collection — recurse into each entry (e.g. interfaces: Dict[str, Interface])
            elif isinstance(value, dict):
                for key, item in value.items():
                    # Each dict entry is a named component (e.g. "Gi0/0/1" → EthernetCsmacdInterface)
                    if isinstance(item, BaseModel):
                        result.update(self._flatten(item, path + (field_name, key)))

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

    def _identity_key(self, model: BaseModel) -> tuple:
        """Extract identity values from a ContainerEntry for matching.
        Returns a tuple of raw values (unwrapped from AttributeValue) from identity_fields."""
        fields = getattr(model, "identity_fields", ())
        values = []
        for f in fields:
            v = getattr(model, f, None)
            # Unwrap AttributeValue to its raw value for hashing
            if isinstance(v, AttributeValue):
                v = v.value
            values.append(v)
        return tuple(values)

    def _make_change(self, op: ComponentDiffOp, path: tuple, before=None, after=None) -> ComponentChange:
        """Build a ComponentChange from an operation, path, and before/after models."""
        obj = after or before
        return ComponentChange(
            op=op,
            path=list(path),
            component_type=type(obj),
            component_name=path[-1] if path else "",
            before=before,
            after=after,
            before_dict=before.model_dump() if before else None,
            after_dict=after.model_dump() if after else None,
            changed_attributes=self._attribute_changes(before, after) if (before and after) else [],
        )

    def _diff_singletons(self, desired: Dict[tuple, BaseModel], observed: Dict[tuple, BaseModel]) -> List[ComponentChange]:
        """Diff leaves that are not ContainerEntry — matched by exact path."""
        changes = []
        all_paths = set(desired) | set(observed)
        for path in all_paths:
            d = desired.get(path)
            o = observed.get(path)
            if d and o:
                if d != o:
                    changes.append(self._make_change(ComponentDiffOp.CHANGE, path, before=o, after=d))
            elif d:
                changes.append(self._make_change(ComponentDiffOp.ADD, path, after=d))
            else:
                changes.append(self._make_change(ComponentDiffOp.REMOVE, path, before=o))
        return changes

    def _diff_entries(self, desired: Dict[tuple, BaseModel], observed: Dict[tuple, BaseModel]) -> List[ComponentChange]:
        """Diff ContainerEntry leaves — matched by identity_fields within each container scope."""
        changes = []

        # Group by container path (parent = path[:-1]) so identity matching is scoped
        desired_by_container: Dict[tuple, Dict[str, BaseModel]] = defaultdict(dict)
        observed_by_container: Dict[tuple, Dict[str, BaseModel]] = defaultdict(dict)

        for path, model in desired.items():
            desired_by_container[path[:-1]][path[-1]] = model
        for path, model in observed.items():
            observed_by_container[path[:-1]][path[-1]] = model

        all_containers = set(desired_by_container) | set(observed_by_container)

        for container_path in all_containers:
            d_components = desired_by_container.get(container_path, {})
            o_components = observed_by_container.get(container_path, {})

            # Build identity → (key, model) lookup for observed
            o_by_identity: Dict[tuple, tuple[str, BaseModel]] = {}
            o_by_key: Dict[str, BaseModel] = dict(o_components)
            for key, model in o_components.items():
                identity = self._identity_key(model)
                if identity:  # non-empty identity_fields — match by field values
                    o_by_identity[identity] = (key, model)

            matched_o_keys = set()

            for d_key, d_model in d_components.items():
                d_identity = self._identity_key(d_model)
                o_key, o_model = None, None

                if d_identity:
                    # Match by identity field values (e.g. same address, same vlan_id)
                    match = o_by_identity.get(d_identity)
                    if match:
                        o_key, o_model = match
                else:
                    # identity_fields = () — fall back to dict key matching
                    if d_key in o_by_key:
                        o_key, o_model = d_key, o_by_key[d_key]

                if o_model:
                    matched_o_keys.add(o_key)
                    if d_model != o_model:
                        changes.append(self._make_change(
                            ComponentDiffOp.CHANGE, container_path + (d_key,),
                            before=o_model, after=d_model,
                        ))
                else:
                    changes.append(self._make_change(
                        ComponentDiffOp.ADD, container_path + (d_key,),
                        after=d_model,
                    ))

            # Remaining observed entries that weren't matched → removed
            for o_key, o_model in o_components.items():
                if o_key not in matched_o_keys:
                    changes.append(self._make_change(
                        ComponentDiffOp.REMOVE, container_path + (o_key,),
                        before=o_model,
                    ))

        return changes

    def diff(self, *, desired_config: ComposedConfiguration, observed_config: ComposedConfiguration) -> Diff:
        """
        Compare two ComposedConfiguration objects and return a component-based diff.

        Singletons (fixed-path leaves like SystemConfig) are matched by path.
        ContainerEntry leaves (dict entries like interfaces) are matched by identity_fields,
        handling cases where keys differ (e.g. "Gi0/0/1" vs "GigabitEthernet0/0/1").
        """
        flat_desired = self._flatten(desired_config)
        flat_observed = self._flatten(observed_config)

        # Split into singletons (path-matched) and entries (identity-matched)
        singleton_d = {p: m for p, m in flat_desired.items() if not isinstance(m, ContainerEntry)}
        singleton_o = {p: m for p, m in flat_observed.items() if not isinstance(m, ContainerEntry)}
        entry_d = {p: m for p, m in flat_desired.items() if isinstance(m, ContainerEntry)}
        entry_o = {p: m for p, m in flat_observed.items() if isinstance(m, ContainerEntry)}

        all_changes = self._diff_singletons(singleton_d, singleton_o) + self._diff_entries(entry_d, entry_o)

        added = [c for c in all_changes if c.op == ComponentDiffOp.ADD]
        removed = [c for c in all_changes if c.op == ComponentDiffOp.REMOVE]
        changed = [c for c in all_changes if c.op == ComponentDiffOp.CHANGE]

        return Diff(
            added=added,
            removed=removed,
            changed=changed,
            total_desired=len(flat_desired),
            total_observed=len(flat_observed),
        )
