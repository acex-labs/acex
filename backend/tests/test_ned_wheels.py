"""NEDs are served as real wheels, even when the backend has them installed editable."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from importlib.metadata import PathDistribution, version

import pytest
from acex.plugins.neds.manager import ned_manager
from acex.plugins.neds.manager.ned_manager import NEDManager
from acex.plugins.neds.manager.wheels import build_wheel


@pytest.fixture
def editable_ned(tmp_path, monkeypatch):
    """A NED laid out like an editable install: its code lives in a source tree, not site-packages."""
    src = tmp_path / "src"
    package = src / "acex_fake_ned"
    (package / "templates").mkdir(parents=True)
    (package / "__init__.py").write_text("class FakeDriver:\n    pass\n")
    (package / "templates" / "config.j2").write_text("hostname {{ name }}\n")
    (package / "__pycache__").mkdir()
    (package / "__pycache__" / "__init__.cpython-313.pyc").write_bytes(b"stale")
    monkeypatch.syspath_prepend(str(src))

    dist_info = tmp_path / "site" / "acex_fake_ned-1.2.3.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: acex-fake-ned\n"
        "Version: 1.2.3\n"
        "Requires-Dist: pytest @ file:///somewhere/else/pytest\n"
        'Requires-Dist: acex-unknown-dep[extra] @ file:///nowhere ; python_version >= "3.13"\n'
        "Requires-Dist: pyyaml (>=6.0.2,<7.0.0)\n"
    )
    (dist_info / "entry_points.txt").write_text("[acex.neds]\nfake = acex_fake_ned:FakeDriver\n")
    (dist_info.parent / "acex_fake_ned.pth").write_text(str(src))
    return PathDistribution(dist_info)


def test_the_wheel_carries_the_code_not_a_pth(editable_ned, tmp_path):
    wheel = build_wheel(editable_ned, "acex_fake_ned", tmp_path)

    names = zipfile.ZipFile(wheel).namelist()
    assert wheel.name == "acex_fake_ned-1.2.3-py3-none-any.whl"
    assert "acex_fake_ned/__init__.py" in names
    assert "acex_fake_ned/templates/config.j2" in names
    assert not [n for n in names if n.endswith(".pth") or "__pycache__" in n or n.endswith("direct_url.json")]


def test_path_dependencies_become_version_requirements(editable_ned, tmp_path):
    wheel = build_wheel(editable_ned, "acex_fake_ned", tmp_path)

    metadata = zipfile.ZipFile(wheel).read("acex_fake_ned-1.2.3.dist-info/METADATA").decode()
    assert "file://" not in metadata
    assert f"Requires-Dist: pytest>={version('pytest')}\n" in metadata
    assert 'Requires-Dist: acex-unknown-dep[extra] ; python_version >= "3.13"\n' in metadata
    assert "Requires-Dist: pyyaml (>=6.0.2,<7.0.0)\n" in metadata


def test_pip_installs_the_wheel(editable_ned, tmp_path):
    wheel = build_wheel(editable_ned, "acex_fake_ned", tmp_path)
    target = tmp_path / "target"

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), str(wheel)],
        check=True,
        capture_output=True,
    )

    assert (target / "acex_fake_ned" / "templates" / "config.j2").is_file()
    assert "acex.neds" in (target / "acex_fake_ned-1.2.3.dist-info" / "entry_points.txt").read_text()


def test_only_built_wheels_can_be_downloaded(monkeypatch, tmp_path):
    wheel = tmp_path / "acex_fake_ned-1.2.3-py3-none-any.whl"
    wheel.write_bytes(b"")
    monkeypatch.setattr(ned_manager, "built_wheels", lambda: {"acex-fake-ned": wheel})

    nm = NEDManager()
    assert nm.wheel_path("acex_fake_ned-1.2.3-py3-none-any.whl") == wheel
    assert nm.wheel_path("../../etc/passwd") is None
    assert nm.wheel_path("other-1.0-py3-none-any.whl") is None
