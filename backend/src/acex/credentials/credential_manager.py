import os
from typing import Optional, List, Dict

from cryptography.fernet import Fernet
from fastapi import HTTPException

from acex.models.credential import (
    Credential,
    CredentialField,
    NodeCredential,
    CREDENTIAL_TYPE_FIELDS,
    CredentialCreate,
    CredentialUpdate,
    CredentialResponse,
    CredentialFieldResponse,
    CredentialSecret,
    NodeCredentialCreate,
    NodeCredentialResponse,
)


class CredentialManager:

    def __init__(self, db_manager, encryption_key: str = None, vault_client=None):
        self.db = db_manager
        key = encryption_key or os.environ.get("ACEX_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError("Encryption key required: pass encryption_key or set ACEX_ENCRYPTION_KEY")
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        self._vault = vault_client

    def _encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    # ── Helpers ──────────────────────────────────────────────────

    def _get_type_fields(self, credential_type: str) -> List[tuple]:
        """Returns [(field_name, sensitive), ...] for a credential type."""
        fields = CREDENTIAL_TYPE_FIELDS.get(credential_type)
        if fields is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown credential type: {credential_type}. "
                       f"Valid types: {', '.join(CREDENTIAL_TYPE_FIELDS.keys())}",
            )
        return fields

    def _validate_fields(self, credential_type: str, fields: Dict[str, str]):
        """Validate that only allowed field names are provided."""
        type_fields = self._get_type_fields(credential_type)
        allowed = {name for name, _ in type_fields}
        unknown = set(fields.keys()) - allowed
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown fields for type '{credential_type}': {', '.join(unknown)}. "
                       f"Allowed: {', '.join(allowed)}",
            )

    def _build_response(self, cred: Credential, fields: List[CredentialField]) -> CredentialResponse:
        return CredentialResponse(
            id=cred.id,
            name=cred.name,
            credential_type=cred.credential_type,
            source=cred.source,
            vault_path=cred.vault_path,
            fields=[
                CredentialFieldResponse(
                    field_name=f.field_name,
                    field_value=self._decrypt(f.field_value) if not f.sensitive else None,
                    sensitive=f.sensitive,
                )
                for f in fields
            ],
        )

    def _save_fields(self, session, credential_id: int, credential_type: str, fields: Dict[str, str]) -> List[CredentialField]:
        """Save fields based on type definition. Sensitivity is derived from the type."""
        type_fields = self._get_type_fields(credential_type)
        sensitive_map = {name: sensitive for name, sensitive in type_fields}

        db_fields = []
        for name, sensitive in type_fields:
            value = fields.get(name, "")
            field = CredentialField(
                credential_id=credential_id,
                field_name=name,
                field_value=self._encrypt(value) if value else self._encrypt(""),
                sensitive=sensitive,
            )
            session.add(field)
            db_fields.append(field)
        return db_fields

    # ── CRUD ─────────────────────────────────────────────────────

    def create(self, payload: CredentialCreate) -> CredentialResponse:
        self._get_type_fields(payload.credential_type)  # validate type exists

        session = next(self.db.get_session())
        try:
            cred = Credential(
                name=payload.name,
                credential_type=payload.credential_type,
                source=payload.source,
                vault_path=payload.vault_path,
            )
            session.add(cred)
            session.flush()

            db_fields = []
            if payload.source != "vault":
                self._validate_fields(payload.credential_type, payload.fields)
                db_fields = self._save_fields(session, cred.id, cred.credential_type, payload.fields)

            session.commit()
            session.refresh(cred)
            return self._build_response(cred, db_fields)
        finally:
            session.close()

    def list(self, name: Optional[str] = None) -> List[CredentialResponse]:
        session = next(self.db.get_session())
        try:
            query = session.query(Credential)
            if name:
                query = query.filter(Credential.name.ilike(f"{name}%"))
            creds = query.order_by(Credential.name).all()

            result = []
            for cred in creds:
                fields = session.query(CredentialField).filter(
                    CredentialField.credential_id == cred.id
                ).all()
                result.append(self._build_response(cred, fields))
            return result
        finally:
            session.close()

    def get(self, id: int) -> CredentialResponse:
        session = next(self.db.get_session())
        try:
            cred = session.get(Credential, id)
            if not cred:
                raise HTTPException(status_code=404, detail="Credential not found")
            fields = session.query(CredentialField).filter(
                CredentialField.credential_id == cred.id
            ).all()
            return self._build_response(cred, fields)
        finally:
            session.close()

    def update(self, id: int, payload: CredentialUpdate) -> CredentialResponse:
        session = next(self.db.get_session())
        try:
            cred = session.get(Credential, id)
            if not cred:
                raise HTTPException(status_code=404, detail="Credential not found")

            if payload.name is not None:
                cred.name = payload.name
            if payload.source is not None:
                cred.source = payload.source
            if payload.vault_path is not None:
                cred.vault_path = payload.vault_path

            if payload.fields is not None:
                self._validate_fields(cred.credential_type, payload.fields)
                session.query(CredentialField).filter(
                    CredentialField.credential_id == cred.id
                ).delete()
                db_fields = self._save_fields(session, cred.id, cred.credential_type, payload.fields)
            else:
                db_fields = session.query(CredentialField).filter(
                    CredentialField.credential_id == cred.id
                ).all()

            session.commit()
            session.refresh(cred)
            return self._build_response(cred, db_fields)
        finally:
            session.close()

    def delete(self, id: int) -> None:
        session = next(self.db.get_session())
        try:
            cred = session.get(Credential, id)
            if not cred:
                raise HTTPException(status_code=404, detail="Credential not found")
            session.query(CredentialField).filter(
                CredentialField.credential_id == cred.id
            ).delete()
            session.delete(cred)
            session.commit()
        finally:
            session.close()

    def get_secret(self, id: int) -> CredentialSecret:
        session = next(self.db.get_session())
        try:
            cred = session.get(Credential, id)
            if not cred:
                raise HTTPException(status_code=404, detail="Credential not found")

            if cred.source == "vault":
                return self._get_vault_secret(cred)

            fields = session.query(CredentialField).filter(
                CredentialField.credential_id == cred.id
            ).all()

            return CredentialSecret(
                id=cred.id,
                credential_type=cred.credential_type,
                fields={f.field_name: self._decrypt(f.field_value) for f in fields},
            )
        finally:
            session.close()

    def _get_vault_secret(self, cred: Credential) -> CredentialSecret:
        if not self._vault:
            raise HTTPException(status_code=501, detail="Vault not configured. Call ae.set_vault() before create_app().")
        if not cred.vault_path:
            raise HTTPException(status_code=400, detail=f"Credential '{cred.name}' has source=vault but no vault_path")

        vault_data = self._vault.read_secret(cred.vault_path)

        # Filter to only the fields defined for this credential type
        type_fields = self._get_type_fields(cred.credential_type)
        allowed = {name for name, _ in type_fields}
        fields = {k: v for k, v in vault_data.items() if k in allowed}

        return CredentialSecret(
            id=cred.id,
            credential_type=cred.credential_type,
            fields=fields,
        )

    # ── Node ↔ Credential mapping ────────────────────────────────

    def assign_to_node(self, node_id: int, payload: NodeCredentialCreate) -> NodeCredentialResponse:
        session = next(self.db.get_session())
        try:
            cred = session.get(Credential, payload.credential_id)
            if not cred:
                raise HTTPException(status_code=404, detail="Credential not found")

            # Prevent duplicate assignment of the same credential to the same node
            existing = session.query(NodeCredential).filter(
                NodeCredential.node_id == node_id,
                NodeCredential.credential_id == payload.credential_id,
            ).first()
            if existing:
                raise HTTPException(status_code=409, detail="Credential already assigned to this node")

            link = NodeCredential(
                node_id=node_id,
                credential_id=payload.credential_id,
            )
            session.add(link)
            session.commit()
            session.refresh(link)
            return NodeCredentialResponse(
                id=link.id,
                node_id=link.node_id,
                credential_id=link.credential_id,
                credential_name=cred.name,
                credential_type=cred.credential_type,
            )
        finally:
            session.close()

    def list_node_credentials(self, node_id: int) -> List[NodeCredentialResponse]:
        session = next(self.db.get_session())
        try:
            links = session.query(NodeCredential).filter(
                NodeCredential.node_id == node_id
            ).all()
            result = []
            for link in links:
                cred = session.get(Credential, link.credential_id)
                result.append(NodeCredentialResponse(
                    id=link.id,
                    node_id=link.node_id,
                    credential_id=link.credential_id,
                    credential_name=cred.name if cred else None,
                    credential_type=cred.credential_type if cred else None,
                ))
            return result
        finally:
            session.close()

    def remove_node_credential(self, node_id: int, credential_id: int) -> None:
        session = next(self.db.get_session())
        try:
            deleted = session.query(NodeCredential).filter(
                NodeCredential.node_id == node_id,
                NodeCredential.credential_id == credential_id,
            ).delete()
            if not deleted:
                raise HTTPException(status_code=404, detail="Assignment not found")
            session.commit()
        finally:
            session.close()

    def get_node_credentials_for_manifest(self, node_ids: List[int]) -> dict:
        """Returns {node_id: {credential_type: credential_id}} for manifest generation."""
        session = next(self.db.get_session())
        try:
            links = session.query(NodeCredential).filter(
                NodeCredential.node_id.in_(node_ids)
            ).all()
            result = {}
            for link in links:
                cred = session.get(Credential, link.credential_id)
                if cred:
                    result.setdefault(link.node_id, {})[cred.credential_type] = link.credential_id
            return result
        finally:
            session.close()
