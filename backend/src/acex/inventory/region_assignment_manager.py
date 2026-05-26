from acex.models.regions import SiteRegionAssignment, SiteRegionAssignmentCreate
from fastapi import HTTPException


class RegionAssignmentManager:

    def __init__(self, db_manager, inventory):
        self.db = db_manager
        self.inventory = inventory

    async def _validate_refs(self, region_name: str, site_name: str):
        regions = await self.inventory.regions.query(name=region_name)
        if not regions.items:
            raise HTTPException(status_code=404, detail=f"Region '{region_name}' not found")

        sites = await self.inventory.sites.query(name=site_name)
        if not sites.items:
            raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")

    async def create_assignment(self, payload: SiteRegionAssignmentCreate) -> SiteRegionAssignment:
        await self._validate_refs(payload.region_name, payload.site_name)

        existing = self.list_assignments(region_name=payload.region_name, site_name=payload.site_name)
        if existing:
            raise HTTPException(status_code=409, detail="Assignment already exists")

        session = next(self.db.get_session())
        try:
            assignment = SiteRegionAssignment.model_validate(payload)
            session.add(assignment)
            session.commit()
            session.refresh(assignment)
            return assignment
        finally:
            session.close()

    def list_assignments(
        self,
        region_name: str = None,
        site_name: str = None,
    ) -> list[SiteRegionAssignment]:
        session = next(self.db.get_session())
        try:
            query = session.query(SiteRegionAssignment)
            if region_name:
                query = query.filter(SiteRegionAssignment.region_name == region_name)
            if site_name:
                query = query.filter(SiteRegionAssignment.site_name == site_name)
            return query.all()
        finally:
            session.close()

    def delete_assignment(self, id: int) -> None:
        session = next(self.db.get_session())
        try:
            assignment = session.get(SiteRegionAssignment, id)
            if not assignment:
                raise HTTPException(status_code=404, detail="SiteRegionAssignment not found")
            session.delete(assignment)
            session.commit()
        finally:
            session.close()
