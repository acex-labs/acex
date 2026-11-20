from acex.models import ManagementConnection, ManagementConnectionBase
from acex_devkit.models.management_connection import ManagementConnectionResponse, ManagementConnectionUpdate
from fastapi import HTTPException
from sqlmodel import select


class ManagementConnectionManager:
    def __init__(self, db_connection):
        self.db = db_connection

    def list_connections(
        self, node_id: int | None = None, limit: int = 100, offset: int = 0
    ) -> list[ManagementConnectionResponse]:

        session = next(self.db.get_session())

        try:
            query = select(ManagementConnection)

            # Filtrera på node_id om det anges
            if node_id is not None:
                query = query.where(ManagementConnection.node_id == node_id)

            # Lägg till limit och offset
            query = query.limit(limit).offset(offset)

            connections = session.exec(query).all()

            # Konvertera till response objekt
            return [ManagementConnectionResponse(**connection.model_dump()) for connection in connections]

        finally:
            session.close()

    def get_connection(self, id: int) -> ManagementConnectionResponse | None:
        session = next(self.db.get_session())
        try:
            connection = session.get(ManagementConnection, id)
            if connection:
                return ManagementConnectionResponse(**connection.model_dump())
            return None
        finally:
            session.close()

    def create_connection(self, payload: ManagementConnectionBase) -> ManagementConnectionResponse:
        session = next(self.db.get_session())
        try:
            # Skapa en ManagementConnection från payload data
            mgmt_connection = ManagementConnection(
                primary=payload.primary,
                node_id=payload.node_id,
                connection_type=payload.connection_type,
                target_ip=payload.target_ip,
            )

            # Lägg till i sessionen
            session.add(mgmt_connection)
            # Commita transaktionen
            session.commit()
            # Refresh för att få det genererade ID:t
            session.refresh(mgmt_connection)

            # Returnera som response objekt
            return ManagementConnectionResponse(**mgmt_connection.model_dump())

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def update_connection(self, id: int, payload: ManagementConnectionUpdate) -> ManagementConnectionResponse:
        """Change the fields that are sent. A field left out or sent as null stays as it is.

        A node has one primary connection, so making a connection primary makes the node's other
        connections give way in the same transaction.
        """
        session = next(self.db.get_session())
        try:
            connection = session.get(ManagementConnection, id)
            if not connection:
                raise HTTPException(status_code=404, detail="ManagementConnection not found")

            for field, value in payload.model_dump(exclude_none=True).items():
                setattr(connection, field, value)

            if payload.primary:
                others = session.exec(
                    select(ManagementConnection).where(
                        ManagementConnection.node_id == connection.node_id,
                        ManagementConnection.id != connection.id,
                        ManagementConnection.primary.is_(True),
                    )
                ).all()
                for other in others:
                    other.primary = False

            session.commit()
            session.refresh(connection)
            return ManagementConnectionResponse(**connection.model_dump())

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def delete_connection(self, id: int) -> bool:
        session = next(self.db.get_session())
        try:
            connection = session.get(ManagementConnection, id)
            if connection:
                session.delete(connection)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
