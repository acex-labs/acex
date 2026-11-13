import os
from pathlib import Path

KIT_ROOT = Path(os.environ.get("IBOS_KIT_ROOT", Path(__file__).resolve().parents[2]))
FIXTURES = KIT_ROOT / "fixtures"
DEVICE_FIXTURES = FIXTURES / "device"
GOLDEN = FIXTURES / "golden"
VARIANTS = FIXTURES / "variants"
REGISTER = KIT_ROOT / "evidence" / "register.toml"
DOCS = KIT_ROOT / "docs"
