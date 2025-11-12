from sqlmodel import SQLModel, Field
from typing import Any

class NtpServerAttributes(SQLModel):
    name: str = None
    address: str = None
    prefer: bool = False