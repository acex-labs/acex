from typing import Optional
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import SQLModel, Field

from acex_devkit.models.credential import (
    CredentialBase as CredentialSchema,
    CredentialFieldBase,
    CredentialFieldResponse,
    CredentialResponse,
    CredentialCreate,
    CredentialUpdate,
    CredentialSecret,
    NodeCredentialCreate,
    NodeCredentialResponse,
)


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
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)


class CredentialField(CredentialFieldBase, SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    credential_id: int = Field(foreign_key="credential.id", index=True)
    field_value: str = Field(default="")


class NodeCredential(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    credential_id: int = Field(foreign_key="credential.id", index=True)


__all__ = [
    "Credential",
    "CredentialField",
    "NodeCredential",
    "CREDENTIAL_TYPE_FIELDS",
    "CredentialFieldResponse",
    "CredentialResponse",
    "CredentialCreate",
    "CredentialUpdate",
    "CredentialSecret",
    "NodeCredentialCreate",
    "NodeCredentialResponse",
]
