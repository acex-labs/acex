

from acex_devkit.models.composed_configuration import ComposedConfiguration


class LogicalNodeResponse(BaseModel):
    hostname: Optional[str] = Field('R1', title='Hostname')
    role: Optional[str] = Field('core', title='Role')
    site: Optional[str] = Field('HQ', title='Site')
    sequence: Optional[int] = Field(1, title='Sequence')
    id: Optional[int] = Field(None, title='Id')
    configuration: Optional[ComposedConfiguration] = ComposedConfiguration()
    meta_data: Optional[Dict[str, Any]] = Field(None, title='Meta Data')

class NodeResponse(BaseModel):
    asset_ref_id: int = Field(..., title='Asset Ref Id')
    asset_ref_type: Optional[AssetRefType] = 'asset'
    logical_node_id: int = Field(..., title='Logical Node Id')
    asset: AssetResponse
    logical_node: LogicalNodeResponse


