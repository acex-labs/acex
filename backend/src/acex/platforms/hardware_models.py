"""The declared hardware models an installation runs: enabled by an administrator, or by an asset of the model
entering the inventory. Never disabled on its own."""

from datetime import UTC, datetime

from acex.models.hardware_model import EnabledHardwareModelRow
from acex_devkit import device_types
from sqlmodel import select


class UnknownHardwareModel(LookupError):
    """Not a declared hardware model."""


class HardwareModelManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def enabled(self) -> set[str]:
        session = next(self.db.get_session())
        try:
            return set(session.exec(select(EnabledHardwareModelRow.hardware_model)).all())
        finally:
            session.close()

    def enable(self, hardware_model: str, *, enabled_by: str) -> None:
        if self.declared(hardware_model) is None:
            raise UnknownHardwareModel(f"{hardware_model!r} is not a declared hardware model.")
        session = next(self.db.get_session())
        try:
            self.enable_in(session, hardware_model, enabled_by=enabled_by)
            session.commit()
        finally:
            session.close()

    def disable(self, hardware_model: str) -> None:
        session = next(self.db.get_session())
        try:
            row = session.get(EnabledHardwareModelRow, self.declared(hardware_model) or hardware_model)
            if row is not None:
                session.delete(row)
                session.commit()
        finally:
            session.close()

    def enable_for_asset(self, hardware_model: str | None, *, enabled_by: str) -> None:
        """Enable the model of an asset entering the inventory, when it is a declared one."""
        session = next(self.db.get_session())
        try:
            self.enable_in(session, hardware_model, enabled_by=enabled_by)
            session.commit()
        finally:
            session.close()

    @classmethod
    def enable_in(cls, session, hardware_model: str | None, *, enabled_by: str) -> None:
        """Enable a declared model as part of `session`, which the caller commits. Undeclared models, and
        models already enabled, are left as they are."""
        model = cls.declared(hardware_model)
        if model is not None and session.get(EnabledHardwareModelRow, model) is None:
            session.add(
                EnabledHardwareModelRow(hardware_model=model, enabled_by=enabled_by, enabled_at=datetime.now(UTC))
            )

    @staticmethod
    def declared(hardware_model: str | None) -> str | None:
        """The model as the devkit declares it, whatever its case; None for one it doesn't."""
        device = device_types.get(hardware_model) if hardware_model else None
        if device is None:
            return None
        return next(m for m in device.models if m.casefold() == hardware_model.casefold())
