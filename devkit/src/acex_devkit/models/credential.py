from pydantic import BaseModel

from acex_devkit.models.base import PersistedResponse


class CredentialFieldBase(BaseModel):
    field_name: str
    sensitive: bool = True


class CredentialBase(BaseModel):
    name: str
    credential_type: str
    source: str = "local"
    vault_path: str | None = None


class CredentialFieldResponse(CredentialFieldBase):
    field_value: str | None = None


class CredentialResponse(PersistedResponse, CredentialBase):
    fields: list[CredentialFieldResponse] = []


class CredentialCreate(CredentialBase):
    fields: dict[str, str]


class CredentialUpdate(BaseModel):
    name: str | None = None
    source: str | None = None
    vault_path: str | None = None
    fields: dict[str, str] | None = None


class CredentialSecret(BaseModel):
    id: int
    credential_type: str
    fields: dict[str, str] = {}


class NodeCredentialCreate(BaseModel):
    credential_id: int


class NodeCredentialResponse(PersistedResponse):
    node_id: int
    credential_id: int
    credential_name: str | None = None
    credential_type: str | None = None
