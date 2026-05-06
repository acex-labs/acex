from typing import Optional, List, Dict
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import SQLModel, Field


# ── Database tables ──────────────────────────────────────────────

class Credential(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    credential_type: str  # "userpass", "token", "ssh_key", "snmp_community", "snmpv3", ...
    source: str = "local"  # "local" or "vault"
    vault_path: Optional[str] = None


class CredentialField(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    credential_id: int = Field(foreign_key="credential.id", index=True)
    field_name: str
    field_value: str = ""  # Fernet-encrypted at rest
    sensitive: bool = True  # If True, hidden in public responses


class NodeCredential(SQLModel, table=True):
    """Maps credentials to nodes. One credential per type per node."""
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


# ── Type definitions (field_name → sensitive) ───────────────────

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


# ── Request / response schemas ───────────────────────────────────

class CredentialCreate(SQLModel):
    name: str
    credential_type: str
    source: str = "local"
    vault_path: Optional[str] = None
    fields: Dict[str, str]  # {field_name: field_value}


class CredentialUpdate(SQLModel):
    name: Optional[str] = None
    source: Optional[str] = None
    vault_path: Optional[str] = None
    fields: Optional[Dict[str, str]] = None  # {field_name: field_value}


class CredentialFieldResponse(SQLModel):
    field_name: str
    field_value: Optional[str] = None  # None when sensitive
    sensitive: bool


class CredentialResponse(SQLModel):
    id: int
    name: str
    credential_type: str
    source: str
    vault_path: Optional[str] = None
    fields: List[CredentialFieldResponse] = []


class CredentialSecret(SQLModel):
    """All fields decrypted — agent use only."""
    id: int
    credential_type: str
    fields: Dict[str, str] = {}


class NodeCredentialCreate(SQLModel):
    credential_id: int


class NodeCredentialResponse(SQLModel):
    id: int
    node_id: int
    credential_id: int
    credential_name: Optional[str] = None
    credential_type: Optional[str] = None
