from enum import StrEnum

from pydantic import BaseModel, model_validator

from acex_devkit.models.base import PersistedResponse


class SnmpAuthProtocol(StrEnum):
    """SNMPv3 authentication protocols, in Telegraf's vocabulary."""

    MD5 = "MD5"
    SHA = "SHA"
    SHA224 = "SHA224"
    SHA256 = "SHA256"
    SHA384 = "SHA384"
    SHA512 = "SHA512"


class SnmpPrivProtocol(StrEnum):
    """SNMPv3 privacy protocols, in Telegraf's vocabulary."""

    DES = "DES"
    AES = "AES"
    AES192 = "AES192"
    AES192C = "AES192C"
    AES256 = "AES256"
    AES256C = "AES256C"


# Per-credential-type enum constraints on field values, keyed by field name.
CREDENTIAL_FIELD_ENUMS: dict[str, dict[str, type[StrEnum]]] = {
    "snmpv3": {
        "auth_protocol": SnmpAuthProtocol,
        "priv_protocol": SnmpPrivProtocol,
    },
}


def _validate_field_enums(credential_type: str, fields: dict[str, str]) -> None:
    constraints = CREDENTIAL_FIELD_ENUMS.get(credential_type, {})
    for field_name, enum_cls in constraints.items():
        value = fields.get(field_name)
        if value is None or value == "":
            continue
        try:
            enum_cls(value)
        except ValueError:
            valid = ", ".join(e.value for e in enum_cls)
            raise ValueError(
                f"Invalid {field_name} '{value}' for credential type '{credential_type}'. Valid: {valid}"
            ) from None


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

    @model_validator(mode="after")
    def _check_field_values(self):
        _validate_field_enums(self.credential_type, self.fields)
        return self


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
