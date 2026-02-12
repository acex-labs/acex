from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, model_validator
from deepdiff import DeepDiff


class DiffOp(str, Enum):
    ADD = "add"
    REMOVE = "remove"
    CHANGE = "change"


class DiffNode(BaseModel):
    op: DiffOp
    before: Optional[Any] = None
    after: Optional[Any] = None
    children: Optional[Dict[str, "DiffNode"]] = None

    @model_validator(mode="after")
    def validate_invariants(self):
        if self.op == DiffOp.ADD:
            assert self.before is None and self.after is not None
        elif self.op == DiffOp.REMOVE:
            assert self.before is not None and self.after is None
        elif self.op == DiffOp.CHANGE:
            assert self.before is not None and self.after is not None
        return self


class Diff(BaseModel):
    root: DiffNode

    def is_empty(self) -> bool:
        return not bool(self.root.children)

    def summary(self) -> dict[str, int]:
        stats = {"add": 0, "remove": 0, "change": 0}

        def walk(node: DiffNode):
            stats[node.op.value] += 1
            if node.children:
                for child in node.children.values():
                    walk(child)

        walk(self.root)
        return stats



class ConfigDiffer:

    def diff(self, *, desired_config: dict, observed_config: dict) -> Diff:
        children = self._diff_dicts(
            desired=desired_config,
            observed=observed_config,
        )

        root = DiffNode(
            op=DiffOp.CHANGE,
            before=observed_config,
            after=desired_config,
            children=children or None,
        )

        return Diff(root=root)

    def _remove_keys(self, obj: dict, keys_to_remove: list[str]) -> dict:
        cleaned = {}

        for k, v in obj.items():
            if k in keys_to_remove:
                continue

            if isinstance(v, dict):
                cleaned[k] = self._remove_keys(v, keys_to_remove)
            else:
                cleaned[k] = v

        return cleaned

    def _diff_dicts(
        self,
        *,
        desired: dict,
        observed: dict,
    ) -> Dict[str, DiffNode]:
        """
        Diff two dicts by traversing down to 'value' attributes and comparing them.
        Returns a hierarchical structure of DiffNodes.
        """

        # Remove metadata:
        ignored_keys = ["metadata"]
        observed = self._remove_keys(observed.model_dump(), ignored_keys)
        desired = self._remove_keys(desired.model_dump(), ignored_keys)

        # Diff
        diff = DeepDiff(
            observed,
            desired
        )

        result: Dict[str, DiffNode] = {}

        # Handle added items
        items_added = diff.get("dictionary_item_added", set())
        for path in items_added:
            keys = self._parse_path(path)
            if keys:
                value = self._get_nested_value(desired, keys)
                self._add_to_result(result, keys, DiffNode(
                    op=DiffOp.ADD,
                    after=value
                ))

        # Handle removed items
        items_removed = diff.get("dictionary_item_removed", set())
        for path in items_removed:
            keys = self._parse_path(path)
            if keys:
                value = self._get_nested_value(observed, keys)
                self._add_to_result(result, keys, DiffNode(
                    op=DiffOp.REMOVE,
                    before=value
                ))

        # Handle changed values
        values_changed = diff.get("values_changed", {})
        for path, change in values_changed.items():
            keys = self._parse_path(path)
            if keys:
                self._add_to_result(result, keys, DiffNode(
                    op=DiffOp.CHANGE,
                    before=change["old_value"],
                    after=change["new_value"]
                ))

        return result

    def _parse_path(self, path: str) -> list[str]:
        """Parse DeepDiff path like "root['key1']['key2']" into ['key1', 'key2']"""
        import re
        matches = re.findall(r"\['([^']+)'\]|\[\"([^\"]+)\"\]", path)
        return [m[0] or m[1] for m in matches]

    def _get_nested_value(self, obj: dict, keys: list[str]) -> Any:
        """Get value from nested dict using list of keys"""
        current = obj
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    def _add_to_result(self, result: Dict[str, DiffNode], keys: list[str], node: DiffNode):
        """Add a DiffNode to the result dict at the appropriate nested location"""
        if not keys:
            return

        if len(keys) == 1:
            # Leaf node
            result[keys[0]] = node
        else:
            # Need to create intermediate nodes
            if keys[0] not in result:
                # Create a CHANGE node as intermediate
                result[keys[0]] = DiffNode(
                    op=DiffOp.CHANGE,
                    before={},
                    after={},
                    children={}
                )
            
            # Ensure it has children dict
            if result[keys[0]].children is None:
                result[keys[0]].children = {}
            
            # Recursively add to children
            self._add_to_result(result[keys[0]].children, keys[1:], node)
    
        