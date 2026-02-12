
from sqlalchemy import Text
from sqlmodel import SQLModel, Field, Column
from pydantic import BaseModel
from typing import Literal, Callable, Optional, Any, Union
from datetime import datetime, timezone
from acex_devkit.models.composed_configuration import ComposedConfiguration


class DeviceConfigBase(SQLModel):
    node_instance_id: str = Field(index=True)
    content: str = Field(sa_column=Column(Text))


class DeviceConfig(DeviceConfigBase): ...


class StoredDeviceConfig(DeviceConfigBase, table=True):
    __tablename__ = "device_config"
    id: Optional[int] = Field(default=None, primary_key=True)
    hash: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class DeviceConfigResponse(BaseModel):
    """Response with either parsed (string) or rendered (ComposedConfiguration) content"""
    node_instance_id: str
    content: Union[str, ComposedConfiguration]
    hash: str
    created_at: datetime

