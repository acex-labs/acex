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

For augments whose target is a singleton (its `COMPONENT_MAPPING` path ends
in `.config`, e.g. `SshServer` → `system.ssh.config`), `target` may also be
the class itself — the instance is then unambiguous::

    context.configuration.add(CiscoSshDhMinSize(
        target=SshServer,
        dh_min_size=2048,
    ))

If the augment's `valid_targets` has exactly one entry AND that entry is a
singleton, `target` may be omitted entirely — it's inferred::

    context.configuration.add(CiscoSshDhMinSize(dh_min_size=2048))

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
    singleton: ClassVar[bool] = True

    def pre_init(self):
        target = self.kwargs.pop("target", None)
        if target is None and len(self.valid_targets) == 1:
            target = self.valid_targets[0]
        if target is None:
            raise ValueError(f"{self.__class__.__name__} requires a 'target' kwarg")

        if not self.__class__.singleton and self.kwargs.get("name") is None:
            raise ValueError(
                f"{self.__class__.__name__} is not a singleton — 'name' is required"
            )

        target_is_class = isinstance(target, type)
        target_type = target if target_is_class else type(target)

        if self.valid_targets and not issubclass(target_type, self.valid_targets):
            valid_names = [c.__name__ for c in self.valid_targets]
            label = f"class {target_type.__name__}" if target_is_class else target_type.__name__
            raise ValueError(
                f"{self.__class__.__name__} cannot target {label}; "
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

        target_is_class = isinstance(target, type)
        target_type = target if target_is_class else type(target)
        mapped = Configuration.COMPONENT_MAPPING.get(target_type)
        if mapped is None:
            raise ValueError(
                f"No COMPONENT_MAPPING entry for {target_type.__name__}; "
                f"cannot use as augment target"
            )
        if isinstance(mapped, Template):
            raise ValueError(
                f"{target_type.__name__}: Template-path targets not yet "
                f"supported for augments"
            )
        # Singletons (path ends in .config) use the path as-is; collections
        # append the target's name as the dict key (matches the convention
        # used by Configuration._pop_all_references).
        if mapped.endswith(".config"):
            return mapped
        if target_is_class:
            raise ValueError(
                f"{target_type.__name__} is not a singleton (path '{mapped}' "
                f"doesn't end with '.config'); pass an instance, not the class, "
                f"as target"
            )
        return f"{mapped}.{target.name}"
