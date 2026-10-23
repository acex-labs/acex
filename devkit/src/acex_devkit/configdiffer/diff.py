"""
Component-based diff model for comparing ComposedConfiguration objects.

This module provides a structured way to identify which ConfigComponents have been
added, removed, or changed when comparing two configurations. This enables drivers
to render device-specific command patches based on the component changes.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, FieldSerializationInfo, computed_field, field_serializer

from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.codec_result import UnmatchedLine
from acex_devkit.models.config_origin import ComponentOrigin
from acex_devkit.models.reference import Reference


class ComponentDiffOp(StrEnum):
    """Operation type for a component change"""

    ADD = "add"
    REMOVE = "remove"
    CHANGE = "change"


class AttributeChange(BaseModel):
    """Represents a change to a single attribute within a component. `before` and `after` hold the
    tree's own objects for drivers; serialized, they are plain values for people to read."""

    model_config = {"arbitrary_types_allowed": True}

    attribute_name: str
    before: Any | None = None
    after: Any | None = None
    # The config component placed at the attribute itself (e.g. HostName at system.config.hostname), when
    # it isn't the component's own.
    origin: ComponentOrigin | None = None

    @field_serializer("before", "after")
    def serialize_value(self, value: Any) -> Any:
        return self.plain(value)

    @classmethod
    def plain(cls, value: Any) -> Any:
        """An attribute value as data: an AttributeValue as its value, a Reference as what it points at,
        a sub-model as its set fields."""
        if isinstance(value, AttributeValue):
            return value.model_dump(mode="json")["value"]
        if isinstance(value, Reference):
            return value.pointer
        if isinstance(value, BaseModel):
            return {k: cls.plain(v) for k, v in value if v not in (None, {}, [])}
        if isinstance(value, dict):
            return {k: cls.plain(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls.plain(v) for v in value]
        return value


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
    path: list[str]  # e.g., ['interfaces', 'GigabitEthernet0-0-1']
    component_type: type[Any]  # e.g., 'FrontpanelPort', 'Loopback', 'Vlan'
    component_name: str  # e.g., 'GigabitEthernet0-0-1', 'Lo0', '100'

    # Actual ConfigComponent objects
    before: Any | None = None
    after: Any | None = None

    # Raw dict representations (for formatters and generic processing)
    before_dict: dict[str, Any] | None = None
    after_dict: dict[str, Any] | None = None

    # For CHANGE operations: list of changed attributes
    changed_attributes: list[AttributeChange] = Field(default_factory=list)

    # The config component behind a declared component: the one placed at or above its path
    origin: ComponentOrigin | None = None

    model_config = {"arbitrary_types_allowed": True}

    @field_serializer("component_type")
    def serialize_component_type(self, v: type[Any]) -> str:
        return v.__name__

    @field_serializer("before_dict", "after_dict")
    def serialize_component(self, value: dict[str, Any] | None, info: FieldSerializationInfo) -> dict[str, Any] | None:
        """The component as plain values, its unset fields left out."""
        component = self.before if info.field_name == "before_dict" else self.after
        return AttributeChange.plain(component) if isinstance(component, BaseModel) else value

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

    added: list[ComponentChange] = Field(default_factory=list)
    removed: list[ComponentChange] = Field(default_factory=list)
    changed: list[ComponentChange] = Field(default_factory=list)

    # Total number of config points in desired/observed configs — populated by ConfigDiffer
    total_desired: int = 0
    total_observed: int = 0

    # Observed lines the driver couldn't parse, so they're in neither tree. They say how far the driver
    # covers the device's configuration, not whether the device is compliant.
    unparsed: list[UnmatchedLine] = Field(default_factory=list)

    @computed_field
    @property
    def undeclared_count(self) -> int:
        """Components on the device that the desired configuration doesn't declare. Not counted in
        compliance; they are what a full-ownership apply would remove."""
        return len(self.removed)

    @computed_field
    @property
    def unparsed_count(self) -> int:
        return len(self.unparsed)

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
    def compliance_percentage(self) -> float | None:
        """
        Percentage of desired config points that are compliant.
        None when nothing is desired: there is nothing to be compliant with.
        """
        if self.total_desired == 0:
            return None
        return round(self.compliant_count / self.total_desired * 100, 2)

    def is_empty(self) -> bool:
        """Check if there are no changes"""
        return not (self.added or self.removed or self.changed)

    def summary(self) -> dict[str, Any]:
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
            "undeclared_count": self.undeclared_count,
            "unparsed_count": self.unparsed_count,
        }

    def get_all_changes(self) -> list[ComponentChange]:
        """Get all changes in a single list"""
        return self.added + self.removed + self.changed

    def get_changes_by_type(self, component_type: str) -> list[ComponentChange]:
        """Get all changes for a specific component type (e.g., 'Loopback')"""
        return [change for change in self.get_all_changes() if change.component_type.__name__ == component_type]

    def get_changes_by_path_prefix(self, path_prefix: list[str]) -> list[ComponentChange]:
        """
        Get all changes under a specific path prefix.

        Example:
            get_changes_by_path_prefix(['interfaces']) -> all interface changes
            get_changes_by_path_prefix(['network_instances', 'default']) -> changes in default VRF
        """
        return [change for change in self.get_all_changes() if change.path[: len(path_prefix)] == path_prefix]
