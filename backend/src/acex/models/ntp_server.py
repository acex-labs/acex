from sqlmodel import SQLModel, Field
from typing import Any

<<<<<<< HEAD
class NtpServerAttributes(SQLModel):
=======
class NtpAttributes(SQLModel):
>>>>>>> 4ccc9e1 (Add support for ntp)
    name: str = None
    address: str = None
    prefer: bool = False