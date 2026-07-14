from pydantic import BaseModel, ConfigDict


class PersistedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
