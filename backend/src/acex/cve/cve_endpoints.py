from datetime import UTC, datetime

from acex.models.cve import CveModelRow
from acex_devkit.models.cve import CveCreate, CveResponse
from sqlmodel import select


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

    def query(self):
        session = next(self.db.get_session())
        try:
            cves = session.exec(select(CveModelRow)).all()
            return [CveResponse.model_validate(cve) for cve in cves]
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
                    cve.raw = item.raw
                    cve.updated_at = refreshed_at

            session.commit()
            return [CveResponse.model_validate(cve) for cve in cves_by_cve_id.values()]
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update(self, cve_id: int, payload: CveCreate) -> CveResponse | None:
        session = next(self.db.get_session())
        try:
            cve = session.get(CveModelRow, cve_id)
            if cve is None:
                return None
            cve.cve_id = payload.cve_id
            cve.published = payload.published
            cve.last_modified = payload.last_modified
            cve.description = payload.description
            cve.cvss_score = payload.cvss_score
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
