from pydantic import BaseModel


class PersistedResponse(BaseModel):
    id: int
