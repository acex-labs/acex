import pytest
from acex_devkit.models.logical_node import LogicalNodeCreate
from pydantic import ValidationError

"""Node instance testing"""

"""Asset testing"""

"""Logical node testing"""


def test_correct_logical_node():
    """Test creating a logical node with correct parameters"""
    node = LogicalNodeCreate(hostname="R1", role="core", site="site1", sequence=1)
    assert node.hostname == "R1"
    assert node.role == "core"
    assert node.site == "site1"
    assert node.sequence == 1


def test_logical_node_missing_hostname():
    """What happens when the hostname is missing"""
    with pytest.raises(ValidationError) as e:
        LogicalNodeCreate(role="core")

    assert "hostname" in str(e.value) and "Field required" in str(e.value)


def test_logical_node_defaults():
    """What happens when only the hostname is provided"""
    node = LogicalNodeCreate(hostname="site1-sw1")
    assert node.site is None
    assert node.sequence is None


def test_incorrect_variable_name():
    """What happens when a user writes the incorrect variable names"""
    with pytest.raises(ValidationError) as e:
        LogicalNodeCreate(name="R1", roles="core")

    assert "hostname" in str(e.value) and "Field required" in str(e.value)
