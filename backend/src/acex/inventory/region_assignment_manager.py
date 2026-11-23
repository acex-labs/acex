from acex.models.regions import Region, RegionAssignmentCreate, SiteRegionAssignment
from fastapi import HTTPException
from sqlmodel import select


def site_names_in_region(db_manager, region_name: str) -> list[str]:
    """The sites that a `region` filter on a list stands for, each once.

    The filter is made for typing into a box, so a part of a name matches every region that has it. But a whole
    region name means that region and no other: `eu` is not also `eu-north`. Names are compared ignoring case. A
    region that exists and has no sites has no sites, however many its neighbours have.
    """
    wanted = region_name.casefold()
    session = next(db_manager.get_session())
    try:
        whole_name = any(name.casefold() == wanted for name in session.exec(select(Region.name)).all())
        assignments = session.exec(
            select(SiteRegionAssignment).where(SiteRegionAssignment.region_name.ilike(f"%{region_name}%"))
        ).all()
    finally:
        session.close()
    if whole_name:
        assignments = [a for a in assignments if a.region_name.casefold() == wanted]
    return sorted({a.site_name for a in assignments})


class RegionAssignmentManager:
    def __init__(self, db_manager, inventory):
        self.db = db_manager
        self.inventory = inventory

    def site_names_in(self, region_name: str) -> list[str]:
        """The sites a `region` filter stands for; see `site_names_in_region`."""
        return site_names_in_region(self.db, region_name)

    async def _validate_refs(self, region_name: str, site_name: str):
        # The name filters are patterns (`eu` also finds `eu-north`), so it is the whole name that must be found.
        regions = await self.inventory.regions.query(name=region_name, limit=None)
        if not any(r.name == region_name for r in regions.items):
            raise HTTPException(status_code=404, detail=f"Region '{region_name}' not found")

        sites = await self.inventory.sites.query(name=site_name, limit=None)
        if not any(s.name == site_name for s in sites.items):
            raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")

    async def create_assignment(self, payload: RegionAssignmentCreate) -> SiteRegionAssignment:
        await self._validate_refs(payload.region_name, payload.site_name)

        existing = [a for a in self.list_assignments_of(payload.region_name) if a.site_name == payload.site_name]
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

    def list_assignments_of(self, region_name: str) -> list[SiteRegionAssignment]:
        """The assignments of the region of exactly this name. `list_assignments` takes a pattern, for the filter
        boxes of the lists, and `eu` would bring in the sites of `eu-north`."""
        return [a for a in self.list_assignments(region_name=region_name) if a.region_name == region_name]

    def list_assignments(
        self,
        region_name: str = None,
        site_name: str = None,
        site_names: list = None,
    ) -> list[SiteRegionAssignment]:
        session = next(self.db.get_session())
        try:
            statement = select(SiteRegionAssignment)
            if region_name:
                statement = statement.where(SiteRegionAssignment.region_name.ilike(f"%{region_name}%"))
            if site_name:
                statement = statement.where(SiteRegionAssignment.site_name == site_name)
            if site_names:
                statement = statement.where(SiteRegionAssignment.site_name.in_(site_names))
            return session.exec(statement).all()
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
