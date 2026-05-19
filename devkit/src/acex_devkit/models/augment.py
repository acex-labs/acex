from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny

# --- Augments --------------------------------------------------------------
# Vendor/os-specific augments mount on target tree components via the
# `Augmentable` mixin. Devkit only knows about `AugmentAttributes` — the
# generic base — and uses `extra='allow'` to round-trip subclass-specific
# fields. Concrete augment payload classes (CiscoDeviceTrackingPolicy-
# Attributes, etc.) live in the backend alongside their ConfigComponent
# classes, so adding a new vendor augment requires no devkit edit.
class AugmentAttributes(BaseModel):
    """
    Base for vendor/os-specific augments that mount on target tree components.

    Subclasses live in the backend (next to their ConfigComponent) and add
    typed payload fields. `extra='allow'` lets those fields round-trip
    through serialize → JSON → re-validate without devkit knowing about them.

    Augments live on a target node's `augments` dict, keyed by `type`. The
    target itself is implicit (it's the node carrying this augment).
    """
    model_config = ConfigDict(extra="allow")
    type: str


class Augmentable(BaseModel):
    """
    Mixin that gives a target node a slot for vendor/os-specific augments.
    Drivers walk `augments` per target and dispatch by augment type; targets
    that no driver augments simply carry an empty dict.

    `SerializeAsAny[AugmentAttributes]` makes Pydantic serialize each value
    using its runtime type (the concrete subclass defined in backend),
    not the declared base type. Combined with `extra='allow'` on
    AugmentAttributes, this round-trips subclass-declared fields through
    serialize → JSON → re-validate without devkit knowing the subclasses.
    """
    augments: Dict[str, SerializeAsAny[AugmentAttributes]] = {}