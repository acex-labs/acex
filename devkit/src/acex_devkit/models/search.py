from enum import StrEnum

from pydantic import BaseModel


class SearchHitType(StrEnum):
    logical_node = "logical_node"
    node_instance = "node_instance"
    site = "site"
    region = "region"
    asset = "asset"
    asset_cluster = "asset_cluster"
    contact = "contact"


class SearchHit(BaseModel):
    id: int
    label: str
    sublabel: str | None = None
    #: The field the search text was found in, and its value there.
    matched_field: str
    matched_value: str


class SearchGroup(BaseModel):
    type: SearchHitType
    #: Every match of this type; `items` holds only the best ones.
    total: int
    items: list[SearchHit]


class SearchResponse(BaseModel):
    query: str
    #: Only the types with at least one match, in a fixed order.
    groups: list[SearchGroup]
