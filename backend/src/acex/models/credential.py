from acex_devkit.models.credential import (
    CredentialBase as CredentialSchema,
)
from acex_devkit.models.credential import (
    CredentialCreate,
    CredentialFieldBase,
    CredentialFieldResponse,
    CredentialResponse,
    CredentialSecret,
    CredentialUpdate,
    NodeCredentialCreate,
    NodeCredentialResponse,
)
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel

CREDENTIAL_TYPE_FIELDS = {
    "userpass": [
        ("username", False),
        ("password", True),
    ],
    "privilege_escalation": [
        ("password", True),
    ],
    "token": [
        ("token", True),
    ],
    "snmp_community": [
        ("community", True),
    ],
    "snmpv3": [
        ("username", False),
        ("auth_protocol", False),
        ("auth_password", True),
        ("priv_protocol", False),
        ("priv_password", True),
    ],
    "ssh_key": [
        ("username", False),
        ("private_key", True),
        ("passphrase", True),
    ],
}


class Credential(CredentialSchema, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)


class CredentialField(CredentialFieldBase, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    credential_id: int = Field(foreign_key="credential.id", index=True)
    field_value: str = Field(default="")


class NodeCredential(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    node_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    credential_id: int = Field(foreign_key="credential.id", index=True)


class SiteCredential(SQLModel, table=True):
    """Maps credentials to sites (e.g. SNMP community string per site)."""

    id: int | None = Field(default=None, primary_key=True)
    site_name: str = Field(index=True)
    credential_id: int = Field(foreign_key="credential.id", index=True)


class SiteCredentialCreate(SQLModel):
    credential_id: int


class SiteCredentialResponse(SQLModel):
    id: int
    site_name: str
    credential_id: int
    credential_name: str | None = None
    credential_type: str | None = None


__all__ = [
    "Credential",
    "CredentialField",
    "NodeCredential",
    "SiteCredential",
    "CREDENTIAL_TYPE_FIELDS",
    "CredentialFieldResponse",
    "CredentialResponse",
    "CredentialCreate",
    "CredentialUpdate",
    "CredentialSecret",
    "NodeCredentialCreate",
    "NodeCredentialResponse",
    "SiteCredentialCreate",
    "SiteCredentialResponse",
]
