from collections import defaultdict
from typing import Any, get_args

from pydantic import BaseModel

from acex_devkit.configdiffer.diff import AttributeChange, ComponentChange, ComponentDiffOp, Diff
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.container_entry import ContainerEntry
from acex_devkit.models.reference import Reference
from acex_devkit.normalizer import MASK


class ConfigDiffer:
    """Diffs desired against observed configuration, component by component.

    Only declared components take part: one identical to what an empty `ComposedConfiguration` already
    holds at its path (an empty container, the default `global` network instance) states no intent and
    is left out on both sides.
    """

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

    def _flatten(self, model: BaseModel, path: tuple = ()) -> dict[tuple, BaseModel]:
        """
        Recursively walk a model tree, collecting leaf nodes.
        A leaf is any BaseModel that has direct AttributeValue fields.
        A model can be both a leaf (stored) and have children (recursed into).
        Returns a flat mapping of path → leaf instance.
        """
        if model is None:
            return {}
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

    def _attribute_changes(self, before: BaseModel, after: BaseModel) -> list[AttributeChange]:
        """Compare an observed (before) and a desired (after) component and return the changed attributes."""
        changes = []
        derived = set(getattr(before, "derived_fields", ())) | set(getattr(after, "derived_fields", ()))
        all_fields = (set(before.model_fields.keys()) | set(after.model_fields.keys())) - derived
        for field_name in all_fields:
            b = getattr(before, field_name, None)
            a = getattr(after, field_name, None)
            if not self._same(b, a):
                changes.append(AttributeChange(attribute_name=field_name, before=b, after=a))
        return changes

    def _same(self, observed: Any, desired: Any) -> bool:
        """References are equal when they point at the same place, whatever path spells it out. A secret
        masked in the observed configuration can't be compared, so it matches any desired value."""
        if isinstance(observed, AttributeValue) and observed.value == MASK:
            return desired is not None
        if isinstance(observed, Reference) and isinstance(desired, Reference):
            return self._position(self.observed, observed.pointer) == self._position(self.desired, desired.pointer)
        if self._is_references(observed) and self._is_references(desired):
            observed_targets = {self._position(self.observed, r.pointer) for r in observed.values()}
            return observed_targets == {self._position(self.desired, r.pointer) for r in desired.values()}
        return observed == desired

    def _is_references(self, value: Any) -> bool:
        return isinstance(value, dict) and all(isinstance(v, Reference) for v in value.values())

    def _position(self, root: BaseModel, pointer: str) -> tuple:
        """Where `pointer` lands in `root`, with each dict key replaced by the entry's identity where it
        has one. The same component keyed differently in two trees gets the same position."""
        node, rest, position = root, pointer, []
        while rest:
            if isinstance(node, dict):
                # Keys may hold dots (`Gi0/1.10`), so the longest key the pointer continues with wins.
                key = max((k for k in node if rest == k or rest.startswith(f"{k}.")), key=len, default=None)
                if key is None:
                    return ("unresolved", pointer)
                node, rest = node[key], rest[len(key) + 1 :]
                identity = self._identity_key(node) if isinstance(node, ContainerEntry) else ()
                position.append(identity or key)
            else:
                segment, _, rest = rest.partition(".")
                node = getattr(node, segment, None)
                if node is None:
                    return ("unresolved", pointer)
                position.append(segment)
        return tuple(position)

    def _declared(self, flat: dict[tuple, BaseModel], defaults: dict[tuple, BaseModel]) -> dict[tuple, BaseModel]:
        """The leaves that state something: those differing from the empty tree's leaf at their path."""
        return {path: model for path, model in flat.items() if defaults.get(path) != model}

    def _masked_match(
        self, desired: BaseModel, observed: dict[str, BaseModel], taken: set[str]
    ) -> tuple[str, BaseModel] | None:
        """An observed entry of the same type known only by a masked secret (an SNMP community string):
        it can't be told apart, so it stands in for the first desired entry left without a match."""
        return next(
            (
                (key, model)
                for key, model in observed.items()
                if key not in taken and type(model) is type(desired) and MASK in self._identity_key(model)
            ),
            None,
        )

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

    def _diff_singletons(
        self, desired: dict[tuple, BaseModel], observed: dict[tuple, BaseModel]
    ) -> list[ComponentChange]:
        """Diff leaves that are not ContainerEntry — matched by exact path."""
        changes = []
        all_paths = set(desired) | set(observed)
        for path in all_paths:
            d = desired.get(path)
            o = observed.get(path)
            if d and o:
                if self._attribute_changes(o, d):
                    changes.append(self._make_change(ComponentDiffOp.CHANGE, path, before=o, after=d))
            elif d:
                changes.append(self._make_change(ComponentDiffOp.ADD, path, after=d))
            else:
                changes.append(self._make_change(ComponentDiffOp.REMOVE, path, before=o))
        return changes

    def _diff_entries(self, desired: dict[tuple, BaseModel], observed: dict[tuple, BaseModel]) -> list[ComponentChange]:
        """Diff ContainerEntry leaves — matched by identity_fields within each container scope."""
        changes = []

        # Group by container path (parent = path[:-1]) so identity matching is scoped
        desired_by_container: dict[tuple, dict[str, BaseModel]] = defaultdict(dict)
        observed_by_container: dict[tuple, dict[str, BaseModel]] = defaultdict(dict)

        for path, model in desired.items():
            desired_by_container[path[:-1]][path[-1]] = model
        for path, model in observed.items():
            observed_by_container[path[:-1]][path[-1]] = model

        all_containers = set(desired_by_container) | set(observed_by_container)

        for container_path in all_containers:
            d_components = desired_by_container.get(container_path, {})
            o_components = observed_by_container.get(container_path, {})

            # Build identity → (key, model) lookup for observed
            o_by_identity: dict[tuple, tuple[str, BaseModel]] = {}
            o_by_key: dict[str, BaseModel] = dict(o_components)
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
                    match = o_by_identity.get(d_identity) or self._masked_match(d_model, o_components, matched_o_keys)
                    if match:
                        o_key, o_model = match
                else:
                    # identity_fields = () — fall back to dict key matching
                    if d_key in o_by_key:
                        o_key, o_model = d_key, o_by_key[d_key]

                if o_model:
                    matched_o_keys.add(o_key)
                    if self._attribute_changes(o_model, d_model):
                        changes.append(
                            self._make_change(
                                ComponentDiffOp.CHANGE,
                                container_path + (d_key,),
                                before=o_model,
                                after=d_model,
                            )
                        )
                else:
                    changes.append(
                        self._make_change(
                            ComponentDiffOp.ADD,
                            container_path + (d_key,),
                            after=d_model,
                        )
                    )

            # Remaining observed entries that weren't matched → removed
            for o_key, o_model in o_components.items():
                if o_key not in matched_o_keys:
                    changes.append(
                        self._make_change(
                            ComponentDiffOp.REMOVE,
                            container_path + (o_key,),
                            before=o_model,
                        )
                    )

        return changes

    def diff(self, *, desired_config: ComposedConfiguration, observed_config: ComposedConfiguration) -> Diff:
        """
        Compare two ComposedConfiguration objects and return a component-based diff.

        Singletons (fixed-path leaves like SystemConfig) are matched by path.
        ContainerEntry leaves (dict entries like interfaces) are matched by identity_fields,
        handling cases where keys differ (e.g. "Gi0/0/1" vs "GigabitEthernet0/0/1").
        """
        self.desired, self.observed = desired_config, observed_config
        defaults = self._flatten(ComposedConfiguration())
        flat_desired = self._declared(self._flatten(desired_config), defaults)
        flat_observed = self._declared(self._flatten(observed_config), defaults)

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
