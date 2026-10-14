"""ZTP DHCP scopes: the IPv4 networks the ZTP DHCP server hands out addresses in.

Rendered, together with the vendor class mapping, into the DHCP config that points devices to their bootstrap.
"""

from datetime import UTC, datetime
from ipaddress import IPv4Network

from acex.models.ztp_dhcp_scope import ZtpDhcpScopeRow
from acex_devkit.models.ztp import ZtpDhcpScopeCreate, ZtpDhcpScopeResponse, ZtpDhcpScopeUpdate
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

REQUIRED = ("network", "pool_start", "pool_end", "gateway")


class ZtpDhcpScopeNotFound(LookupError):
    pass


class InvalidDhcpScope(ValueError):
    """The scope doesn't hold together, or overlaps another one."""


class ZtpDhcpScopeManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def list_scopes(self) -> list[ZtpDhcpScopeResponse]:
        session = next(self.db.get_session())
        try:
            rows = session.exec(select(ZtpDhcpScopeRow)).all()
            scopes = [ZtpDhcpScopeResponse.model_validate(row) for row in rows]
            return sorted(scopes, key=lambda scope: scope.network)
        finally:
            session.close()

    def create(self, payload: ZtpDhcpScopeCreate, *, updated_by: str) -> ZtpDhcpScopeResponse:
        session = next(self.db.get_session())
        try:
            return self._save(session, ZtpDhcpScopeRow(), payload, updated_by)
        finally:
            session.close()

    def update(self, id: int, payload: ZtpDhcpScopeUpdate, *, updated_by: str) -> ZtpDhcpScopeResponse:
        """Change the fields sent in `payload`; those left out keep their value."""
        changes = payload.model_dump(include=payload.model_fields_set)
        cleared = [field for field in REQUIRED if field in changes and changes[field] is None]
        if cleared:
            raise InvalidDhcpScope(f"A scope needs {', '.join(cleared)}.")
        if "dns_servers" in changes and changes["dns_servers"] is None:
            changes["dns_servers"] = []
        session = next(self.db.get_session())
        try:
            row = self._row(session, id)
            current = ZtpDhcpScopeResponse.model_validate(row).model_dump(include=set(ZtpDhcpScopeCreate.model_fields))
            scope = ZtpDhcpScopeCreate(**{**current, **changes})
            return self._save(session, row, scope, updated_by)
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
    def _row(session, id: int) -> ZtpDhcpScopeRow:
        row = session.get(ZtpDhcpScopeRow, id)
        if row is None:
            raise ZtpDhcpScopeNotFound(f"No DHCP scope with id {id}.")
        return row

    @staticmethod
    def _check(session, scope: ZtpDhcpScopeCreate, id: int | None) -> None:
        network = scope.network
        if not (network.network_address < scope.pool_start <= scope.pool_end < network.broadcast_address):
            raise InvalidDhcpScope(f"The pool must be an ascending range of host addresses in {network}.")
        if scope.gateway not in network or scope.gateway in (network.network_address, network.broadcast_address):
            raise InvalidDhcpScope(f"The gateway must be a host address in {network}.")
        if scope.pool_start <= scope.gateway <= scope.pool_end:
            raise InvalidDhcpScope("The gateway can't be in the pool.")
        for other in session.exec(select(ZtpDhcpScopeRow).where(ZtpDhcpScopeRow.id != id)).all():
            if IPv4Network(other.network).overlaps(network):
                raise InvalidDhcpScope(f"{network} overlaps the scope {other.network}.")

    @classmethod
    def _save(cls, session, row: ZtpDhcpScopeRow, scope: ZtpDhcpScopeCreate, updated_by: str) -> ZtpDhcpScopeResponse:
        cls._check(session, scope, row.id)
        row.network = str(scope.network)
        row.pool_start = str(scope.pool_start)
        row.pool_end = str(scope.pool_end)
        row.gateway = str(scope.gateway)
        row.dns_servers = [str(server) for server in scope.dns_servers]
        row.domain_name = (scope.domain_name or "").strip() or None
        row.description = (scope.description or "").strip() or None
        row.updated_by = updated_by
        row.updated_at = datetime.now(UTC)
        session.add(row)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise InvalidDhcpScope(f"A scope for {scope.network} already exists.") from exc
        session.refresh(row)
        return ZtpDhcpScopeResponse.model_validate(row)
