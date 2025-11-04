from sqlmodel import SQLModel, Field
from typing import Any

class SingleAttribute(SQLModel):
    value: Any = None
    kind: str = None