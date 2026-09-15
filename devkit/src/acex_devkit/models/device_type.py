"""Hardware device type contracts.

Every supported hardware model is declared as a subclass of :class:`DeviceType`.
Subclassing registers the model, so adding a device is adding a class - no
registry to update and no data file to keep in sync.

What lives here is the contract: facts about the physical device that hold no
matter which driver talks to it.

* **Identity** - vendor, OS, and the model strings the device reports. This is
  what the API validates against and what the UI offers as selectable options.
* **Layout** - the front-panel ports, declared as a few :class:`PortGroup` runs
  and expanded into :class:`InterfaceSlot` positions.

What does NOT live here is syntax. Interface names, index offsets and speed
prefixes are per-platform rendering concerns and belong to the driver, which
derives them from ``os`` and ``stackable``.
"""

from collections.abc import Mapping
from enum import IntEnum, StrEnum
from typing import ClassVar

from pydantic import BaseModel, Field, model_validator

from acex_devkit.models.asset import OS, Vendor


class Speed(IntEnum):
    """Interface speed in kbps, as reported in device capabilities."""

    fast_ethernet = 100_000
    gigabit = 1_000_000
    two_and_half_gigabit = 2_500_000
    five_gigabit = 5_000_000
    ten_gigabit = 10_000_000
    twentyfive_gigabit = 25_000_000
    forty_gigabit = 40_000_000
    hundred_gigabit = 100_000_000
    fourhundred_gigabit = 400_000_000


class PortMedia(StrEnum):
    """Front-panel connector type.

    Speed alone does not say what plugs in: a 1G RJ-45 port and a 1G SFP cage
    are the same speed and different hardware.
    """

    rj45 = "rj45"
    sfp = "sfp"
    sfp_plus = "sfp+"
    sfp28 = "sfp28"
    qsfp_plus = "qsfp+"
    qsfp28 = "qsfp28"


class PortGroup(BaseModel):
    """A contiguous run of identical front-panel ports."""

    count: int = Field(gt=0)
    speeds: list[Speed] = Field(min_length=1)
    module_index: int = 0
    media: PortMedia | None = None


class InterfaceSlot(BaseModel):
    """One expanded physical port position.

    Indices are zero-based physical positions. Applying platform offsets and
    rendering a name is the driver's job.
    """

    module_index: int
    index: int
    speed_capabilities: list[int] = Field(default_factory=list)
    media: PortMedia | None = None


class PortModule(BaseModel):
    """A pluggable port-bearing module, such as a C9300-NM-8X uplink module.

    Declared like a device: subclassing registers the module by every model
    string it reports. A module owns only ports - which slot it sits in, and
    therefore how its ports are numbered, is decided by the device.
    """

    models: list[str] = Field(default_factory=list, min_length=1)
    ports: list[PortGroup] = Field(default_factory=list)
    notes: str | None = None

    registry: ClassVar[dict[str, type["PortModule"]]] = {}
    abstract: ClassVar[bool] = True

    def __init_subclass__(cls, abstract: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.abstract = abstract

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        if cls.abstract:
            return
        for name in cls.model_fields["models"].get_default(call_default_factory=True):
            key = name.casefold()
            existing = PortModule.registry.get(key)
            if existing is not None and existing is not cls:
                raise ValueError(f"duplicate port module {name!r}: {existing.__name__} and {cls.__name__}")
            PortModule.registry[key] = cls

    @property
    def primary_model(self) -> str:
        return self.models[0]

    @property
    def port_count(self) -> int:
        return sum(g.count for g in self.ports)

    @classmethod
    def get(cls, model: str) -> type["PortModule"] | None:
        return cls.registry.get(model.casefold())


class ModuleSlot(BaseModel):
    """A position on a device that accepts a pluggable :class:`PortModule`.

    ``index`` is the module number the device uses when numbering the slot's
    ports. ``accepts`` lists the module models that physically fit; empty means
    unconstrained. ``default`` names the module shipped from the factory, if any.
    """

    index: int
    accepts: list[str] = Field(default_factory=list)
    default: str | None = None

    def permits(self, module_model: str) -> bool:
        if not self.accepts:
            return True
        return module_model.casefold() in {a.casefold() for a in self.accepts}


class DeviceType(BaseModel):
    """Base class for all hardware model declarations."""

    # --- identity -------------------------------------------------------
    models: list[str] = Field(default_factory=list, min_length=1)
    os: list[OS] = Field(default_factory=list, min_length=1)
    vendor: Vendor

    # --- physical facts -------------------------------------------------
    ports: list[PortGroup] = Field(default_factory=list)
    slots: list[ModuleSlot] = Field(default_factory=list)
    stackable: bool = True

    notes: str | None = None

    # --- registry -------------------------------------------------------
    registry: ClassVar[dict[str, type["DeviceType"]]] = {}
    abstract: ClassVar[bool] = True

    def __init_subclass__(cls, abstract: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.abstract = abstract

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """Register concrete subclasses by every model string they declare.

        Pydantic calls this once the subclass is fully built; ``__init_subclass__``
        runs too early to read ``model_fields``.
        """
        super().__pydantic_init_subclass__(**kwargs)
        if cls.abstract:
            return
        for name in cls.model_fields["models"].get_default(call_default_factory=True):
            key = name.casefold()
            existing = DeviceType.registry.get(key)
            if existing is not None and existing is not cls:
                raise ValueError(f"duplicate hardware model {name!r}: {existing.__name__} and {cls.__name__}")
            DeviceType.registry[key] = cls

    @model_validator(mode="after")
    def _check_identity(self):
        if any(not m.strip() for m in self.models):
            raise ValueError("model names must not be blank")
        return self

    # --- derived --------------------------------------------------------
    @property
    def primary_model(self) -> str:
        return self.models[0]

    @property
    def port_count(self) -> int:
        return sum(g.count for g in self.ports)

    def interfaces(self, fitted: Mapping[int, str] | None = None) -> list[InterfaceSlot]:
        """Expand this device into zero-based physical port positions.

        Args:
            fitted: Which module model occupies each slot index, as observed on
                the asset. Slots left out fall back to the slot's ``default``;
                slots with neither contribute no ports.

        Raises:
            ValueError: if a fitted module is unknown, or does not fit the slot.
        """
        groups = list(self.ports)
        for slot in self.slots:
            model = (fitted or {}).get(slot.index, slot.default)
            if model is None:
                continue
            if not slot.permits(model):
                raise ValueError(f"{self.primary_model} slot {slot.index} does not accept {model!r}")
            klass = PortModule.get(model)
            if klass is None:
                raise ValueError(f"unknown port module {model!r}")
            groups += [g.model_copy(update={"module_index": slot.index}) for g in klass().ports]

        expanded: list[InterfaceSlot] = []
        next_index: dict[int, int] = {}
        for group in groups:
            start = next_index.get(group.module_index, 0)
            for offset in range(group.count):
                expanded.append(
                    InterfaceSlot(
                        module_index=group.module_index,
                        index=start + offset,
                        speed_capabilities=[int(sp) for sp in group.speeds],
                        media=group.media,
                    )
                )
            next_index[group.module_index] = start + group.count
        return sorted(expanded, key=lambda i: (i.module_index, i.index))

    @property
    def slot_indices(self) -> list[int]:
        """Module positions this device can populate, lowest first."""
        return sorted(s.index for s in self.slots)

    @classmethod
    def get(cls, hardware_model: str) -> type["DeviceType"] | None:
        """Look up a declared device type by any of its model strings."""
        return cls.registry.get(hardware_model.casefold())
