from datetime import UTC, datetime

from acex_devkit.models.cve import CveCreate, CveModel, CveResponse

class CveManager:
    def __init__(self, db_manager):
        self.db = db_manager

    #def _new_job(self, spec: JobType, data: BaseModel | dict, *, created_by: str) -> Job:
    #    validated = spec.data.model_validate(data)
    #    subject_type, subject_id = None, None
    #    if spec.subject is not None:
    #        subject_type, field = spec.subject
    #        subject_id = getattr(validated, field)
    #    return Job(
    #        type=spec.name,
    #        data=validated.model_dump(mode="json"),
    #        subject_type=subject_type,
    #        subject_id=subject_id,
    #        created_by=created_by,
    #    )

    def get(self, id: int) -> CveResponse | None:
        session = next(self.db.get_session())
        try:
            cve = session.get(CveModel, id)
            return CveResponse.model_validate(cve) if cve is not None else None
        finally:
            session.close()

    def create(self, payload: CveCreate) -> CveResponse:
        """Create new CVE"""
        session = next(self.db.get_session())
        try:
            cve = CveModel.model_validate(payload)
            session.add(cve)
            session.commit()
            session.refresh(cve)
            return CveResponse.model_validate(cve)
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
    def bulk_create(self, payload: list[CveCreate]) -> list[CveResponse]:
        """Create multiple CVEs"""
        session = next(self.db.get_session())
        try:
            cves = []
            for item in payload:
                cve = CveModel.model_validate(item)
                session.add(cve)
                cves.append(cve)
            session.commit()
            for cve in cves:
                session.refresh(cve)
            return [CveResponse.model_validate(cve) for cve in cves]
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()