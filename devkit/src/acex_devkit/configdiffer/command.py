from pydantic import BaseModel, Field
from typing import Optional, Tuple


class Context(BaseModel):
    path: Tuple[str, ...] = Field(default_factory=tuple)
    # priority: int = 100 även här??

    model_config = {
        "frozen": True,  # immutable
    }

class Command(BaseModel):
    context: Context
    command: str
    # priority: int = 100 # För att lägga ordning på commandon sinsemellan

    model_config = {
        "frozen": True,
    }

