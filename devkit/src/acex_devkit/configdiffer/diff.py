"""
Component-based diff model for comparing ComposedConfiguration objects.

This module provides a structured way to identify which ConfigComponents have been
added, removed, or changed when comparing two configurations. This enables drivers
to render device-specific command patches based on the component changes.
"""

from pydantic import BaseModel, Field, field_serializer, computed_field
from typing import Any, Dict, List, Optional, Type
from enum import Enum

from acex_devkit.models.attribute_value import AttributeValue


class ComponentDiffOp(str, Enum):
    """Operation type for a component change"""
    ADD = "add"
    REMOVE = "remove"
    CHANGE = "change"


class AttributeChange(BaseModel):
    """Represents a change to a single attribute within a component"""
    model_config = {"arbitrary_types_allowed": True}

    attribute_name: str
    before: Optional[Any] = None
    after: Optional[Any] = None


class ComponentChange(BaseModel):
    """
    Represents a change to a ConfigComponent.
    
    This is the core structure that drivers will use to render patches.
    It contains:
    - The component path (e.g., ['interfaces', 'GigabitEthernet0-0-1'])
    - The operation type (add/remove/change)
    - The component class name (e.g., 'FrontpanelPort', 'Loopback')
    - The full before/after component data (serialized dicts)
    - The actual ConfigComponent objects (for driver access)
    - Individual attribute changes (for CHANGE operations)
    """
    op: ComponentDiffOp
    path: List[str]  # e.g., ['interfaces', 'GigabitEthernet0-0-1']
    component_type: Type[Any]  # e.g., 'FrontpanelPort', 'Loopback', 'Vlan'
    component_name: str  # e.g., 'GigabitEthernet0-0-1', 'Lo0', '100'
    
    # Actual ConfigComponent objects
    before: Optional[Any] = None
    after: Optional[Any] = None

    # Raw dict representations (for formatters and generic processing)
    before_dict: Optional[Dict[str, Any]] = None
    after_dict: Optional[Dict[str, Any]] = None
    
    # For CHANGE operations: list of changed attributes
    changed_attributes: List[AttributeChange] = Field(default_factory=list)
    
    model_config = {"arbitrary_types_allowed": True}

    @field_serializer("component_type")
    def serialize_component_type(self, v: Type[Any]) -> str:
        return v.__name__

    @property
    def component_type_name(self) -> str:
        """Return the class name of the component type, e.g., 'FrontpanelPort'"""
        return self.component_type.__name__

    def get_path_str(self, separator: str = "/") -> str:
        """Return the component path as a string, e.g., 'interfaces/GigabitEthernet0-0-1'"""
        return separator.join(self.path) if self.path else ""


class Diff(BaseModel):
    """
    Result of comparing two ComposedConfiguration objects.
    
    This provides a component-centric view of what changed, suitable for
    rendering device-specific patches.
    """
    added: List[ComponentChange] = Field(default_factory=list)
    removed: List[ComponentChange] = Field(default_factory=list)
    changed: List[ComponentChange] = Field(default_factory=list)

    # Total number of config points in desired/observed configs — populated by ConfigDiffer
    total_desired: int = 0
    total_observed: int = 0

    @computed_field
    @property
    def compliant_count(self) -> int:
        """
        Number of desired config points that are fully compliant (present and
        identical on the device). Equals total desired minus points that are
        missing (added) or incorrect (changed).
        """
        return max(0, self.total_desired - len(self.added) - len(self.changed))

    @computed_field
    @property
    def compliance_percentage(self) -> float:
        """
        Percentage of desired config points that are compliant.
        Returns 100.0 when there are no desired config points.
        """
        if self.total_desired == 0:
            return 100.0
        return round(self.compliant_count / self.total_desired * 100, 2)

    def is_empty(self) -> bool:
        """Check if there are no changes"""
        return not (self.added or self.removed or self.changed)

    def summary(self) -> Dict[str, Any]:
        """Get a summary of changes and compliance metadata"""
        return {
            "added": len(self.added),
            "removed": len(self.removed),
            "changed": len(self.changed),
            "total_changes": len(self.added) + len(self.removed) + len(self.changed),
            "total_desired": self.total_desired,
            "total_observed": self.total_observed,
            "compliant_count": self.compliant_count,
            "compliance_percentage": self.compliance_percentage,
        }

    def get_all_changes(self) -> List[ComponentChange]:
        """Get all changes in a single list"""
        return self.added + self.removed + self.changed

    def get_changes_by_type(self, component_type: str) -> List[ComponentChange]:
        """Get all changes for a specific component type (e.g., 'Loopback')"""
        return [
            change for change in self.get_all_changes()
            if change.component_type.__name__ == component_type
        ]

    def get_changes_by_path_prefix(self, path_prefix: List[str]) -> List[ComponentChange]:
        """
        Get all changes under a specific path prefix.
        
        Example:
            get_changes_by_path_prefix(['interfaces']) -> all interface changes
            get_changes_by_path_prefix(['network_instances', 'default']) -> changes in default VRF
        """
        return [
            change for change in self.get_all_changes()
            if change.path[:len(path_prefix)] == path_prefix
        ]
