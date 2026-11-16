from enum import Enum
from typing import Literal, Optional, Union

from acex.api.routers.config_components import (
    _build_catalog,
    _enum_values,
    _type_label,
    _unwrap_attribute_value,
)
from acex_devkit.models import AttributeValue


class Action(Enum):
    TRAP = "trap"
    SHUTDOWN = "shutdown"


# `X | None` and `Optional[X]` are different objects before Python 3.14, so these tests spell out both.
def test_optional_attribute_value_is_unwrapped_in_both_union_syntaxes():
    for annotation in (AttributeValue[int] | None, Optional[AttributeValue[int]]):  # noqa: UP045
        assert _unwrap_attribute_value(annotation) == (int, True)


def test_required_attribute_value_is_not_optional():
    assert _unwrap_attribute_value(AttributeValue[str]) == (str, False)


def test_optional_field_that_is_not_an_attribute_value_gives_no_type():
    assert _unwrap_attribute_value(int | None) == (None, True)


def test_union_of_types_gets_one_label_in_both_syntaxes():
    assert _type_label(int | str) == "string"
    assert _type_label(Union[int, str]) == "string"  # noqa: UP007


def test_enum_values_are_found_inside_a_union_in_both_syntaxes():
    choices = ["trap", "shutdown"]
    assert _enum_values(Action | None) == choices
    assert _enum_values(Optional[Action]) == choices  # noqa: UP045
    assert _enum_values(Optional[Literal["trap", "shutdown"]]) == choices  # noqa: UP045


def test_catalog_lists_the_optional_attributes_of_a_vlan():
    vlan = next(c for c in _build_catalog().components if c.name == "Vlan")
    fields = {f.name: f for f in vlan.fields}

    assert {"name", "vlan_id", "vlan_name", "network_instance"} <= set(fields)
    assert fields["name"].required
    assert not fields["vlan_id"].required
    assert fields["vlan_id"].type == "integer"
