from pydantic import BaseModel
from typing import Optional, Dict, List

from acex_devkit.models.base import PersistedResponse


class CredentialFieldBase(BaseModel):
    field_name: str
    sensitive: bool = True


class CredentialBase(BaseModel):
    name: str
    credential_type: str
    source: str = "local"
    vault_path: Optional[str] = None


class CredentialFieldResponse(CredentialFieldBase):
    field_value: Optional[str] = None


class CredentialResponse(PersistedResponse, CredentialBase):
    fields: List[CredentialFieldResponse] = []


class CredentialCreate(CredentialBase):
    fields: Dict[str, str]


class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    source: Optional[str] = None
    vault_path: Optional[str] = None
    fields: Optional[Dict[str, str]] = None


class CredentialSecret(BaseModel):
    id: int
    credential_type: str
    fields: Dict[str, str] = {}


class NodeCredentialCreate(BaseModel):
    credential_id: int


class NodeCredentialResponse(PersistedResponse):
    node_id: int
    credential_id: int
    credential_name: Optional[str] = None
    credential_type: Optional[str] = None
