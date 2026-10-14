"""Packaging the NEDs installed in the backend as wheels that workers and agents can install.

A NED is packaged from the code Python actually imports, not from the files its
distribution lists: an editable install lists only a .pth pointing at a source
tree that exists on this machine alone. Path dependencies (`x @ file://...`) are
rewritten to version requirements for the same reason.
"""

from __future__ import annotations

import atexit
import base64
import functools
import hashlib
import importlib.util
import logging
import re
import shutil
import tempfile
import zipfile
from importlib.metadata import Distribution, PackageNotFoundError, entry_points, version
from pathlib import Path

log = logging.getLogger(__name__)

_TAG = "py3-none-any"

# Requires-Dist: name[extras] @ file:///some/path ; marker
_PATH_REQUIREMENT = re.compile(r"^Requires-Dist:\s*([A-Za-z0-9._-]+)(\[[^\]]*\])?\s*@\s*file://\S*\s*(;.*)?$")


def wheel_filename(dist_name: str, dist_version: str) -> str:
    return f"{re.sub(r'[-_.]+', '_', dist_name)}-{dist_version}-{_TAG}.whl"


@functools.cache
def built_wheels() -> dict[str, Path]:
    """Every installed NED packaged as a wheel, keyed by distribution name.

    Built once per process into a fresh temporary directory, so a wheel always
    matches the code that is installed now.
    """
    out_dir = Path(tempfile.mkdtemp(prefix="acex-neds-"))
    atexit.register(shutil.rmtree, out_dir, ignore_errors=True)

    wheels: dict[str, Path] = {}
    for ep in entry_points(group="acex.neds"):
        dist = ep.dist
        if dist is None or dist.name in wheels:
            continue
        try:
            wheels[dist.name] = build_wheel(dist, ep.module.split(".")[0], out_dir)
        except Exception:
            log.exception(f"Could not package NED {dist.name} {dist.version} as a wheel")
    return wheels


def build_wheel(dist: Distribution, package: str, out_dir: Path) -> Path:
    """Package the importable `package` of `dist` as a wheel in `out_dir`."""
    files = _package_files(package)
    dist_info = f"{re.sub(r'[-_.]+', '_', dist.name)}-{dist.version}.dist-info"
    generated = {
        f"{dist_info}/METADATA": _metadata(dist).encode(),
        f"{dist_info}/WHEEL": f"Wheel-Version: 1.0\nGenerator: acex\nRoot-Is-Purelib: true\nTag: {_TAG}\n".encode(),
    }
    entry_points_txt = dist.read_text("entry_points.txt")
    if entry_points_txt:
        generated[f"{dist_info}/entry_points.txt"] = entry_points_txt.encode()

    wheel_path = out_dir / wheel_filename(dist.name, dist.version)
    record: list[str] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, src in files.items():
            data = src.read_bytes()
            zf.writestr(arcname, data)
            record.append(_record_line(arcname, data))
        for arcname, data in generated.items():
            zf.writestr(arcname, data)
            record.append(_record_line(arcname, data))
        record.append(f"{dist_info}/RECORD,,")
        zf.writestr(f"{dist_info}/RECORD", "\n".join(record) + "\n")

    log.info(f"Packaged NED {dist.name} {dist.version} as {wheel_path.name}")
    return wheel_path


def _package_files(package: str) -> dict[str, Path]:
    """The files of an importable package or module, keyed by their path in the wheel."""
    spec = importlib.util.find_spec(package)
    if spec is None:
        raise ModuleNotFoundError(f"{package} is not importable")
    if not spec.submodule_search_locations:
        origin = Path(spec.origin)
        return {origin.name: origin}

    root = Path(next(iter(spec.submodule_search_locations)))
    return {
        f"{package}/{path.relative_to(root).as_posix()}": path
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def _metadata(dist: Distribution) -> str:
    """The distribution's METADATA, with path dependencies turned into version requirements."""
    lines = []
    for line in (dist.read_text("METADATA") or "").splitlines():
        match = _PATH_REQUIREMENT.match(line)
        if match:
            name, extras, marker = match.group(1), match.group(2) or "", match.group(3)
            line = f"Requires-Dist: {name}{extras}{_version_floor(name)}"
            if marker:
                line += f" {marker}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _version_floor(name: str) -> str:
    # At least what the backend runs with: the NED was developed against it.
    try:
        return f">={version(name)}"
    except PackageNotFoundError:
        return ""


def _record_line(arcname: str, data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{arcname},sha256={digest},{len(data)}"
