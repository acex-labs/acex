from sqlmodel import SQLModel, Field
from typing import Optional, Dict

class LogicalNodeBase(SQLModel):
    hostname: str = Field(default="R1")
    role: str = Field(default="core")
    site: Optional[str] = Field(default="HQ")
    sequence: Optional[int] = Field(default=1)

class LogicalNode(LogicalNodeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class LogicalNodeCreate(LogicalNodeBase):
    pass

class LogicalNodeResponse(LogicalNodeBase):
    id: Optional[int] = Field(default=None)
    configuration: Dict = Field(default_factory=dict)
    meta_data: Dict = Field(default_factory=dict)

class LogicalNodeListResponse(LogicalNodeBase):
    id: int