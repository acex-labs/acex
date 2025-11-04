
from sqlalchemy import Text
from sqlmodel import SQLModel, Field, Column
from typing import Literal, Callable, Optional, Any
from datetime import datetime, timezone


class DeviceConfigBase(SQLModel):
    node_instance_id: str = Field(index=True)
    content: str = Field(sa_column=Column(Text))


class DeviceConfig(DeviceConfigBase): ...


class StoredDeviceConfig(DeviceConfigBase, table=True):
    __tablename__ = "device_config"
    id: Optional[int] = Field(default=None, primary_key=True)
    hash: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

