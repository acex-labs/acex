from acex.models.contacts import ContactAssignment, ContactAssignmentCreate
from fastapi import HTTPException


class ContactAssignmentManager:

    def __init__(self, db_manager, inventory):
        self.db = db_manager
        self.inventory = inventory

    async def _validate_refs(self, contact_name: str, site_name: str):
        """Validera att både contact och site existerar."""
        contacts = await self.inventory.contacts.query(name=contact_name)
        if not contacts:
            raise HTTPException(status_code=404, detail=f"Contact '{contact_name}' not found")

        sites = await self.inventory.sites.query(name=site_name)
        if not sites:
            raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")

    async def create_assignment(self, payload: ContactAssignmentCreate) -> ContactAssignment:
        await self._validate_refs(payload.contact_name, payload.site_name)
        session = next(self.db.get_session())
        try:
            assignment = ContactAssignment.model_validate(payload)
            session.add(assignment)
            session.commit()
            session.refresh(assignment)
            return assignment
        finally:
            session.close()

    def list_assignments(
        self,
        contact_name: str = None,
        site_name: str = None,
    ) -> list[ContactAssignment]:
        session = next(self.db.get_session())
        try:
            query = session.query(ContactAssignment)
            if contact_name:
                query = query.filter(ContactAssignment.contact_name == contact_name)
            if site_name:
                query = query.filter(ContactAssignment.site_name == site_name)
            return query.all()
        finally:
            session.close()

    def delete_assignment(self, id: int) -> None:
        session = next(self.db.get_session())
        try:
            assignment = session.get(ContactAssignment, id)
            if not assignment:
                raise HTTPException(status_code=404, detail="ContactAssignment not found")
            session.delete(assignment)
            session.commit()
        finally:
            session.close()
