"""The platform catalog: what a client needs to fill in an asset or a policy, in the order the form asks for it.

Which vendors we have hardware declarations for, which hardware models each makes, which OS a model can run, and
of those which an installed NED supports and which the installation has enabled. Version examples are keyed by OS,
since they do not vary by model. Derived from the devkit and NED declarations, so adding one shows up here with no
change on this side.
"""

from acex.platforms.hardware_models import HardwareModelManager
from acex.plugins.neds.manager import NEDManager
from acex_devkit import device_types as catalog
from acex_devkit.models.ned import Platform
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS
from acex_devkit.models.platform_catalog import PlatformCatalog, PlatformModel, PlatformVendor


class PlatformCatalogBuilder:
    def __init__(self, hardware_models: HardwareModelManager):
        self.hardware_models = hardware_models

    def build(self) -> PlatformCatalog:
        enabled = self.hardware_models.enabled()
        platforms = NEDManager().platforms()
        vendors = []
        for vendor in catalog.vendors():
            by_model: dict[str, set[OS]] = {}
            for device in catalog.device_types(vendor=vendor):
                for model in device.models:
                    by_model.setdefault(model, set()).update(device.os)
            vendors.append(
                PlatformVendor(
                    vendor=vendor,
                    hardware_models=[
                        PlatformModel(
                            hardware_model=model,
                            operating_systems=sorted(os),
                            supported_os=sorted(o for o in os if self.supports(platforms, vendor, model, o)),
                            enabled=model in enabled,
                        )
                        for model, os in sorted(by_model.items())
                    ],
                )
            )
        return PlatformCatalog(vendors=vendors, version_examples=self.version_examples())

    @staticmethod
    def supports(platforms: list[Platform], vendor, hardware_model: str, os: OS) -> bool:
        """Whether a NED declares the model, or every model of the vendor, on the OS, at some version."""
        return any(
            (p.vendor, p.os) == (vendor, os) and (p.hardware_models is None or hardware_model in p.hardware_models)
            for p in platforms
        )

    @staticmethod
    def version_examples() -> dict[OS, list[str]]:
        examples = {}
        for os in OS:
            scheme = OsVersionScheme.for_os(os)
            if scheme and scheme.examples:
                examples[os] = scheme.examples
        return examples
