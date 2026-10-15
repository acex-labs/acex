"""ZTP vendor classes: the DHCP vendor classes devices send, each mapped to the ZTP method it bootstraps with.

The mapping decides, once acex renders DHCP config, which bootstrap a device is pointed to.
"""

from datetime import UTC, datetime

from acex.models.ztp_vendor_class import ZtpVendorClassRow
from acex_devkit.models.ztp import (
    ZtpVendorClassCreate,
    ZtpVendorClassMatch,
    ZtpVendorClassResponse,
    ZtpVendorClassUpdate,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import select


class ZtpVendorClassNotFound(LookupError):
    pass


class VendorClassExists(ValueError):
    """Another row already has the vendor class."""


class AmbiguousVendorClass(ValueError):
    """A device could match this vendor class and another one mapped to a different method."""


class ZtpVendorClassManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def list_vendor_classes(self) -> list[ZtpVendorClassResponse]:
        session = next(self.db.get_session())
        try:
            rows = session.exec(select(ZtpVendorClassRow).order_by(ZtpVendorClassRow.vendor_class)).all()
            return [ZtpVendorClassResponse.model_validate(row) for row in rows]
        finally:
            session.close()

    def create(self, payload: ZtpVendorClassCreate, *, updated_by: str) -> ZtpVendorClassResponse:
        row = ZtpVendorClassRow(
            vendor_class=self._clean(payload.vendor_class),
            match=payload.match,
            method=payload.method,
            updated_by=updated_by,
            updated_at=datetime.now(UTC),
        )
        session = next(self.db.get_session())
        try:
            return self._save(session, row)
        finally:
            session.close()

    def update(self, id: int, payload: ZtpVendorClassUpdate, *, updated_by: str) -> ZtpVendorClassResponse:
        """Change the fields sent in `payload`; those left out keep their value."""
        changes = payload.model_dump(include=payload.model_fields_set)
        if "vendor_class" in changes:
            changes["vendor_class"] = self._clean(changes["vendor_class"])
        session = next(self.db.get_session())
        try:
            row = self._row(session, id)
            for field, value in changes.items():
                setattr(row, field, value)
            row.updated_by = updated_by
            row.updated_at = datetime.now(UTC)
            return self._save(session, row)
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
    def _clean(vendor_class: str | None) -> str:
        vendor_class = (vendor_class or "").strip()
        if not vendor_class:
            raise ValueError("A vendor class can't be empty.")
        if "'" in vendor_class:
            # Kea expressions quote strings with ' and have no escape for it.
            raise ValueError("A vendor class can't contain '.")
        return vendor_class

    @staticmethod
    def _row(session, id: int) -> ZtpVendorClassRow:
        row = session.get(ZtpVendorClassRow, id)
        if row is None:
            raise ZtpVendorClassNotFound(f"No vendor class with id {id}.")
        return row

    @staticmethod
    def _matches_with(row: ZtpVendorClassRow, other: ZtpVendorClassRow) -> bool:
        """Whether some vendor class a device sends would match both."""
        return (row.match == ZtpVendorClassMatch.prefix and other.vendor_class.startswith(row.vendor_class)) or (
            other.match == ZtpVendorClassMatch.prefix and row.vendor_class.startswith(other.vendor_class)
        )

    @classmethod
    def _save(cls, session, row: ZtpVendorClassRow) -> ZtpVendorClassResponse:
        if row.method is not None:
            with session.no_autoflush:
                others = session.exec(select(ZtpVendorClassRow).where(ZtpVendorClassRow.id != row.id)).all()
            for other in others:
                if other.method not in (None, row.method) and cls._matches_with(row, other):
                    raise AmbiguousVendorClass(
                        f"A device could match both '{row.vendor_class}' and '{other.vendor_class}', "
                        f"which is mapped to {other.method}."
                    )
        session.add(row)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise VendorClassExists(f"Vendor class '{row.vendor_class}' already exists.") from exc
        session.refresh(row)
        return ZtpVendorClassResponse.model_validate(row)
