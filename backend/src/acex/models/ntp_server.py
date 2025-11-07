from sqlmodel import SQLModel, Field
from typing import Any

class NtpAttributes(SQLModel):
    name: str = None
    address: str = None
    prefer: bool = False