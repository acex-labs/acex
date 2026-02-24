from pydantic import BaseModel, model_validator
from typing import Any, Dict, Optional, List, Iterator
from enum import Enum


class DiffOp(str, Enum):
    ADD = "add"
    REMOVE = "remove"
    CHANGE = "change"


class DiffNode(BaseModel):
    op: DiffOp
    path: list[str] = []  # Path to this node in the composed model, e.g., ['interfaces', 'GigabitEthernet0-0-1', 'description']
    obj: Optional[Any] = None  # The ConfigComponent object this diff refers to (for component-level changes)
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
    
    def path_str(self, separator: str = "/") -> str:
        """Return the path as a string, e.g., 'interfaces/GigabitEthernet0-0-1/description'"""
        return separator.join(self.path) if self.path else ""
    
    def get_component_path(self) -> tuple[list[str], str | None]:
        """
        Split path into component path and attribute name.
        Returns (component_path, attribute_name)
        
        Examples:
            ['interfaces', 'GigabitEthernet0-0-1', 'description'] 
            -> (['interfaces', 'GigabitEthernet0-0-1'], 'description')
            
            ['interfaces', 'GigabitEthernet0-0-1']
            -> (['interfaces', 'GigabitEthernet0-0-1'], None)
        """
        if len(self.path) == 0:
            return ([], None)
        elif len(self.path) == 1:
            return (self.path, None)
        else:
            return (self.path[:-1], self.path[-1])
    
    def get_changed_attribute(self) -> str | None:
        """
        Get the name of the attribute that changed.
        
        Example:
            path = ['interfaces', 'GigabitEthernet0-0-1', 'description']
            Returns 'description'
        """
        _, attr = self.get_component_path()
        return attr


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
    
    def iter_all_nodes(self) -> Iterator[DiffNode]:
        """Iterate over all DiffNodes in the tree (including intermediate nodes)"""
        def walk(node: DiffNode):
            yield node
            if node.children:
                for child in node.children.values():
                    yield from walk(child)
        
        yield from walk(self.root)
    
    def iter_leaf_nodes(self) -> Iterator[DiffNode]:
        """Iterate over only leaf DiffNodes (actual attribute changes on ConfigComponents)
        
        This traverses the entire tree until it finds nodes that represent actual
        attribute changes, not just intermediate dictionary/object containers.
        """
        ...
    
    def iter_by_op(self, op: DiffOp) -> Iterator[DiffNode]:
        """Iterate over DiffNodes filtered by operation type
        
        Args:
            op: The operation type to filter by (ADD, REMOVE, or CHANGE)
            
        Yields:
            DiffNode: Leaf nodes matching the specified operation
        """
        ...
