"""Software policy: the software versions approved per vendor, or per hardware model, one of them golden.
A version not approved is not allowed."""

from datetime import UTC, datetime

from acex.models.asset import Asset
from acex.models.software_policy import SoftwarePolicyRow
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.policy import (
    SoftwarePolicyCreate,
    SoftwarePolicyResponse,
    SoftwarePolicyUpdate,
    SoftwareVersionInUse,
)
from sqlalchemy import func
from sqlmodel import select


class SoftwarePolicyNotFound(LookupError):
    pass


class SoftwarePolicyConflict(ValueError):
    """The version is already approved, or another version is already golden, for the vendor and model."""


class SoftwarePolicyManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def list_policies(self) -> list[SoftwarePolicyResponse]:
        """Vendor by vendor, the vendor's own versions before its models', the golden version first."""
        session = next(self.db.get_session())
        try:
            rows = session.exec(select(SoftwarePolicyRow)).all()
            rows = sorted(
                rows,
                key=lambda r: (r.vendor, r.hardware_model is not None, r.hardware_model or "", not r.golden, r.os),
            )
            return [SoftwarePolicyResponse.model_validate(row) for row in rows]
        finally:
            session.close()

    def versions_in_use(self, vendor: Vendor, os: OS, hardware_model: str | None = None) -> list[SoftwareVersionInUse]:
        """The versions assets of the vendor, or of one of its models, report on the OS; newest first."""
        statement = (
            select(Asset.os_version, func.count())
            .where(Asset.vendor == vendor, Asset.os == os, Asset.os_version.is_not(None))
            .group_by(Asset.os_version)
        )
        if hardware_model:
            statement = statement.where(func.lower(Asset.hardware_model) == hardware_model.casefold())
        session = next(self.db.get_session())
        try:
            counts = session.exec(statement).all()
        finally:
            session.close()
        scheme = OsVersionScheme.for_os(os)
        keyed = [
            (scheme.normalize(version) if scheme and scheme.accepts(version) else None, version, count)
            for version, count in counts
        ]
        # Versions the scheme orders, newest first; after them any it can't, by name.
        ordered = sorted((k for k in keyed if k[0] is not None), key=lambda k: k[0], reverse=True)
        ordered += sorted((k for k in keyed if k[0] is None), key=lambda k: k[1])
        return [SoftwareVersionInUse(os_version=version, assets=count) for _, version, count in ordered]

    def get(self, id: int) -> SoftwarePolicyResponse:
        session = next(self.db.get_session())
        try:
            return SoftwarePolicyResponse.model_validate(self._row(session, id))
        finally:
            session.close()

    def create(self, payload: SoftwarePolicyCreate, *, updated_by: str) -> SoftwarePolicyResponse:
        session = next(self.db.get_session())
        try:
            return self._save(session, SoftwarePolicyRow(**payload.model_dump(mode="json")), updated_by)
        finally:
            session.close()

    def update(self, id: int, payload: SoftwarePolicyUpdate, *, updated_by: str) -> SoftwarePolicyResponse:
        """Change the fields sent in `payload`; those left out keep their value. The version as a whole is
        checked again, since a new OS may not accept the version kept."""
        session = next(self.db.get_session())
        try:
            row = self._row(session, id)
            current = SoftwarePolicyResponse.model_validate(row).model_dump(exclude={"id", "updated_by", "updated_at"})
            merged = SoftwarePolicyCreate(**{**current, **payload.model_dump(include=payload.model_fields_set)})
            for field, value in merged.model_dump(mode="json").items():
                setattr(row, field, value)
            return self._save(session, row, updated_by)
        finally:
            session.close()

    def delete(self, id: int) -> None:
        session = next(self.db.get_session())
        try:
            session.delete(self._row(session, id))
            session.commit()
        finally:
            session.close()

    @staticmethod
    def _row(session, id: int) -> SoftwarePolicyRow:
        row = session.get(SoftwarePolicyRow, id)
        if row is None:
            raise SoftwarePolicyNotFound(f"No software policy with id {id}.")
        return row

    @staticmethod
    def _save(session, row: SoftwarePolicyRow, updated_by: str) -> SoftwarePolicyResponse:
        """Save a validated `row`, unless it repeats an approved version or is a second golden one."""
        statement = select(SoftwarePolicyRow).where(
            SoftwarePolicyRow.vendor == row.vendor,
            SoftwarePolicyRow.hardware_model.is_(None)
            if row.hardware_model is None
            else SoftwarePolicyRow.hardware_model == row.hardware_model,
        )
        if row.id is not None:
            statement = statement.where(SoftwarePolicyRow.id != row.id)
        with session.no_autoflush:
            others = session.exec(statement).all()
        where = f"{row.vendor} {row.hardware_model or '(every model)'}"
        key = SoftwarePolicyCreate.version_key(row.os, row.os_version)
        for other in others:
            if other.os == row.os and SoftwarePolicyCreate.version_key(other.os, other.os_version) == key:
                raise SoftwarePolicyConflict(f"{row.os} {row.os_version} is already approved for {where}.")
            if other.golden and row.golden:
                raise SoftwarePolicyConflict(f"{where} already has a golden version: {other.os} {other.os_version}.")
        row.updated_by = updated_by
        row.updated_at = datetime.now(UTC)
        session.add(row)
        session.commit()
        session.refresh(row)
        return SoftwarePolicyResponse.model_validate(row)
