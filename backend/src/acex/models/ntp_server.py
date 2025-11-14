from sqlmodel import SQLModel, Field
from typing import Any

<<<<<<< HEAD
<<<<<<< HEAD
class NtpServerAttributes(SQLModel):
=======
class NtpAttributes(SQLModel):
>>>>>>> 4ccc9e1 (Add support for ntp)
=======
class NtpServerAttributes(SQLModel):
>>>>>>> 3fccc02 (Changed so that variable and class names follow pascal/peb8 standard)
    name: str = None
    address: str = None
    prefer: bool = False