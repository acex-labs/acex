from sqlmodel import SQLModel, Field
from typing import Any

class SshServerAttributes(SQLModel):
    name: str = None
    enable: bool = True
    protocol_version: int = 2
    timeout: int = None
    auth_retries: int = None