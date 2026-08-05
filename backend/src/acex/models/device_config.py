from datetime import datetime

from acex_devkit.models.composed_configuration import ComposedConfiguration
from pydantic import BaseModel
from sqlalchemy import Text
from sqlmodel import Column, Field, SQLModel


class DeviceConfigBase(SQLModel):
    node_instance_id: str = Field(index=True)
    content: str = Field(sa_column=Column(Text))


class DeviceConfig(DeviceConfigBase): ...


class StoredDeviceConfig(DeviceConfigBase, table=True):
    __tablename__ = "device_config"
    id: int | None = Field(default=None, primary_key=True)
    hash: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class DeviceConfigResponse(BaseModel):
    """Response with either parsed (string) or rendered (ComposedConfiguration) content"""

    node_instance_id: str
    content: str | ComposedConfiguration
    hash: str
    created_at: datetime
