import json
import time
from pathlib import Path

_STORE_PATH = Path.home() / ".acex" / "token.json"


def save(data: dict) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.chmod(0o700) if _STORE_PATH.parent.exists() else None
    _STORE_PATH.write_text(json.dumps(data))
    _STORE_PATH.chmod(0o600)


def load() -> dict | None:
    if not _STORE_PATH.exists():
        return None
    return json.loads(_STORE_PATH.read_text())


def clear() -> None:
    if _STORE_PATH.exists():
        _STORE_PATH.unlink()


def is_expired(token_data: dict, buffer_seconds: int = 30) -> bool:
    expires_at = token_data.get("expires_at", 0)
    return time.time() >= (expires_at - buffer_seconds)
