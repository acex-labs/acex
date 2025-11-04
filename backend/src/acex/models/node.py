from sqlmodel import SQLModel, Field
from typing import Optional, Dict

class NodeBase(SQLModel):
    asset_id: str
    logical_node_id: str

class Node(NodeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class NodeResponse(NodeBase):
    asset: Dict = Field(default_factory=dict)
    logical_node: Dict = Field(default_factory=dict)
