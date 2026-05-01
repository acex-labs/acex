"""
Base class for vendor/os-specific augments.

Augments are mounted directly on their target tree component's `augments`
slot, keyed by the augment's `type` discriminator. Drivers that don't
support a given augment type silently ignore it (no renderer registered).

The integrator API stays simple::

    context.configuration.add(CiscoDeviceTrackingPolicy(
        name="...",
        target=interface_or_template,
        policy_name="...",
    ))

`name` and `target` are integrator-side fields used by `Configuration` to
route the augment; they don't appear on the rendered `AugmentAttributes`
payload (location IS target, dict key IS the type discriminator).
"""
from string import Template
from typing import ClassVar, Tuple, Type

from acex.configuration.components.base_component import ConfigComponent


class Augment(ConfigComponent):
    """
    Base for vendor/os-specific augments that mount on tree components.

    Subclasses set:
      - `valid_targets`: tuple of allowed Python target types (ConfigComponent
        classes the augment can attach to)
      - `default_vendor`: informational; not currently materialized in the
        rendered payload (vendor is implicit in `type` discriminator prefix)

    The target's tree path is resolved via `Configuration.COMPONENT_MAPPING`,
    so any registered ConfigComponent type is a candidate target without
    Augment needing per-type handling.
    """
    valid_targets: ClassVar[Tuple[Type[ConfigComponent], ...]] = ()
    default_vendor: ClassVar[str] = None

    def pre_init(self):
        target = self.kwargs.pop("target", None)
        if target is None:
            raise ValueError(f"{self.__class__.__name__} requires a 'target' kwarg")

        if self.valid_targets and not isinstance(target, self.valid_targets):
            valid_names = [c.__name__ for c in self.valid_targets]
            raise ValueError(
                f"{self.__class__.__name__} cannot target {type(target).__name__}; "
                f"valid targets: {valid_names}"
            )

        # Stash on the component for Configuration to use during as_model().
        # Not put back into kwargs — these are routing data, not model fields.
        self._target = target
        self._target_path = self._compute_target_path(target)

    @staticmethod
    def _compute_target_path(target):
        """Resolve target's tree path via COMPONENT_MAPPING (lazy-import)."""
        # Lazy import: configuration.py imports Augment, so importing it
        # at module load would create a cycle.
        from acex.configuration.configuration import Configuration

        mapped = Configuration.COMPONENT_MAPPING.get(type(target))
        if mapped is None:
            raise ValueError(
                f"No COMPONENT_MAPPING entry for {type(target).__name__}; "
                f"cannot use as augment target"
            )
        if isinstance(mapped, Template):
            raise ValueError(
                f"{type(target).__name__}: Template-path targets not yet "
                f"supported for augments"
            )
        # Singletons (path ends in .config) use the path as-is; collections
        # append the target's name as the dict key (matches the convention
        # used by Configuration._pop_all_references).
        if mapped.endswith(".config"):
            return mapped
        return f"{mapped}.{target.name}"
