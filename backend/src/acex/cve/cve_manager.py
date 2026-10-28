from datetime import UTC, datetime

from acex.models.cve import CveModelRow
from acex_devkit.models import PaginatedResponse
from acex_devkit.models.cve import CveCreate, CveResponse, CveUpdate
from sqlmodel import func, select


class CveManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def get(self, cve_id: int) -> CveResponse | None:
        session = next(self.db.get_session())
        try:
            cve = session.get(CveModelRow, cve_id)
            return CveResponse.model_validate(cve) if cve is not None else None
        finally:
            session.close()

    def query(self, limit: int = 100, offset: int = 0) -> PaginatedResponse[CveResponse]:
        session = next(self.db.get_session())
        try:
            total = session.exec(select(func.count()).select_from(CveModelRow)).one()
            rows = session.exec(select(CveModelRow).order_by(CveModelRow.id).offset(offset).limit(limit)).all()
            return PaginatedResponse(
                items=[CveResponse.model_validate(r) for r in rows],
                total=total,
                limit=limit,
                offset=offset,
            )
        finally:
            session.close()

    def create(self, payload: CveCreate) -> CveResponse:
        """Create one CVE."""
        session = next(self.db.get_session())
        try:
            cve = CveModelRow.model_validate(payload)
            session.add(cve)
            session.commit()
            session.refresh(cve)
            return CveResponse.model_validate(cve)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def bulk_create(self, payload: list[CveCreate]) -> list[CveResponse]:
        """Insert or refresh CVEs in one transaction, keyed by their NVD CVE ID."""
        records = {item.cve_id: item for item in payload}
        if not records:
            return []

        session = next(self.db.get_session())
        try:
            existing = session.exec(select(CveModelRow).where(CveModelRow.cve_id.in_(records))).all()
            cves_by_cve_id = {cve.cve_id: cve for cve in existing}
            refreshed_at = datetime.now(UTC)

            for cve_id, item in records.items():
                cve = cves_by_cve_id.get(cve_id)
                if cve is None:
                    cve = CveModelRow.model_validate(item)
                    session.add(cve)
                    cves_by_cve_id[cve_id] = cve
                else:
                    cve.published = item.published
                    cve.last_modified = item.last_modified
                    cve.description = item.description
                    cve.cvss_score = item.cvss_score
                    cve.base_severity = item.base_severity
                    cve.raw = item.raw
                    cve.updated_at = refreshed_at

            session.commit()
            return [CveResponse.model_validate(cve) for cve in cves_by_cve_id.values()]
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update(self, cve_id: int, payload: CveUpdate) -> CveResponse | None:
        session = next(self.db.get_session())
        try:
            cve = session.get(CveModelRow, cve_id)
            if cve is None:
                return None
            cve.description = payload.description
            cve.cvss_score = payload.cvss_score
            cve.base_severity = payload.base_severity
            cve.raw = payload.raw
            cve.updated_at = datetime.now(UTC)
            session.commit()
            session.refresh(cve)
            return CveResponse.model_validate(cve)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
