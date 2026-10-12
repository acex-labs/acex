"""ZTP methods: what an administrator has chosen for each way a device can bootstrap.

The methods themselves are code (`ZtpMethod`). Each has a row here for the
choices: the NED discovery uses, and the temporary login the bootstrap gives a device.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import entry_points

from acex.models.ztp_method import ZtpMethodRow
from acex_devkit.models.ztp import ZTP_METHOD_INFO, ZtpMethod, ZtpMethodResponse, ZtpMethodUpdate
from sqlalchemy.exc import IntegrityError
from sqlmodel import select


class UnknownNed(ValueError):
    """The chosen NED is not installed in the backend, so no worker can be handed it."""


def installed_neds() -> set[str]:
    """NED names as the API lists them: the class name of each `acex.neds` entry point."""
    return {entry_point.value.split(":")[-1] for entry_point in entry_points(group="acex.neds")}


class ZtpMethodManager:
    def __init__(self, db_manager, neds: Callable[[], set[str]] = installed_neds):
        self.db = db_manager
        self.neds = neds

    def list_methods(self) -> list[ZtpMethodResponse]:
        session = next(self.db.get_session())
        try:
            rows = {row.method: row for row in self._rows(session)}
            return [self._response(rows[method]) for method in ZtpMethod]
        finally:
            session.close()

    def get(self, method: ZtpMethod) -> ZtpMethodResponse:
        session = next(self.db.get_session())
        try:
            self._rows(session)
            return self._response(session.get(ZtpMethodRow, method.value))
        finally:
            session.close()

    def update(self, method: ZtpMethod, payload: ZtpMethodUpdate, *, updated_by: str) -> ZtpMethodResponse:
        """Change the fields sent in `payload`; those left out keep their value."""
        changes = payload.model_dump(include=payload.model_fields_set)
        ned = changes.get("ned")
        if ned is not None and ned not in self.neds():
            raise UnknownNed(f"No NED named '{ned}' is installed.")
        session = next(self.db.get_session())
        try:
            self._rows(session)
            row = session.get(ZtpMethodRow, method.value)
            for field, value in changes.items():
                setattr(row, field, value)
            row.updated_by = updated_by
            row.updated_at = datetime.now(UTC)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._response(row)
        finally:
            session.close()

    def _rows(self, session) -> list[ZtpMethodRow]:
        """Every method's row, adding those for methods newer than the database."""
        rows = session.exec(select(ZtpMethodRow)).all()
        missing = {method.value for method in ZtpMethod} - {row.method for row in rows}
        if missing:
            session.add_all(ZtpMethodRow(method=method) for method in missing)
            try:
                session.commit()
            except IntegrityError:
                # Another request added them first.
                session.rollback()
            rows = session.exec(select(ZtpMethodRow)).all()
        return rows

    @staticmethod
    def _response(row: ZtpMethodRow) -> ZtpMethodResponse:
        method = ZtpMethod(row.method)
        return ZtpMethodResponse(
            method=method,
            **ZTP_METHOD_INFO[method].model_dump(),
            ned=row.ned,
            bootstrap_username=row.bootstrap_username,
            bootstrap_password=row.bootstrap_password,
            updated_by=row.updated_by,
            updated_at=row.updated_at,
        )
