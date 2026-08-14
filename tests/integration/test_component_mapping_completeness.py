"""
Guardrail test — every concrete ConfigComponent subclass must be registered
in Configuration.COMPONENT_MAPPING.

When this test fails, it means someone added a new component class without
adding its mapping entry. The symptom in production is a crash during
as_model() traversal (AttributeError: 'X' object has no attribute 'Y')
because the unmapped component is silently skipped and references resolve
to wrong paths.

Abstract base classes (ConfigComponent, Interface, Augment, Routing) are
excluded — only their concrete subclasses need mapping entries.
"""

from acex.configuration.configuration import Configuration


def test_all_concrete_components_are_mapped():
    missing = Configuration.unmapped_components()
    assert missing == [], (
        f"Concrete ConfigComponent subclasses missing from COMPONENT_MAPPING: {missing}. "
        f"Add them to Configuration.COMPONENT_MAPPING in configuration.py."
    )
