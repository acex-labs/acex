"""What a render or parse knows about the device beyond the configuration tree."""

from typing import Any

from acex_devkit.models.node_response import NodeInstance
from acex_devkit.models.os_version import OsVersion, OsVersionScheme


class Context:
    """The node being rendered or parsed, and through its asset the OS version that picks between a
    line's version-bound variants (`Line(..., since="16")`). Drivers subclass it to carry more, e.g.
    the hardware that names interfaces. A cluster takes its first member's version."""

    def __init__(self, node: NodeInstance | None):
        self.node = node
        self.version = self.read_version(node)

    @staticmethod
    def read_version(node: NodeInstance | None) -> OsVersion | None:
        asset: Any = getattr(node, "asset", None)
        if getattr(asset, "type", None) == "asset_cluster":
            asset = next(iter(asset.assets), None)
        raw, os = getattr(asset, "os_version", None), getattr(asset, "os", None)
        scheme = OsVersionScheme.for_os(os) if raw and os else None
        return scheme.normalize(raw) if scheme else None

    def within(self, since: str | None, until: str | None) -> bool | None:
        """Whether the device's version is at least `since` and below `until`, both dotted release
        numbers like "16" or "16.9"; None when the version isn't known."""
        if self.version is None:
            return None
        version = (self.version.major, self.version.minor, self.version.patch or 0)
        return (since is None or version >= self.bound(since)) and (until is None or version < self.bound(until))

    @staticmethod
    def bound(release: str) -> tuple[int, int, int]:
        numbers = [int(part) for part in release.split(".")]
        return tuple((numbers + [0, 0, 0])[:3])
