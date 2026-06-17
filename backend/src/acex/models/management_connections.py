from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import SQLModel, Field
from typing import Optional

from acex_devkit.models.management_connection import (
    ManagementConnectionBase as ManagementConnectionSchema,
    ManagementConnectionResponse,
    ConnectionType,
)


class ManagementConnectionBase(ManagementConnectionSchema, SQLModel):
    node_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )


class ManagementConnection(ManagementConnectionBase, table=True):
    __tablename__ = "mgmt_connection"
    id: int = Field(primary_key=True)


class DeviceManagement(SQLModel):
    asset_id: int
    logical_node_id: int
