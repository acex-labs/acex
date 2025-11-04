from typing import List, Optional
from acex.models import ManagementConnection, ManagementConnectionResponse, ManagementConnectionBase


class ManagementConnectionManager:

    def __init__(self, db_connection):
        self.db = db_connection
        
    def list_connections(
        self, 
        node_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
        ) -> List[ManagementConnectionResponse]:

        session = next(self.db.get_session())

        try:
            query = session.query(ManagementConnection)
            
            # Filtrera på node_id om det anges
            if node_id is not None:
                query = query.filter(ManagementConnection.node_id == node_id)
            
            # Lägg till limit och offset
            query = query.limit(limit).offset(offset)
            
            connections = query.all()
            
            # Konvertera till response objekt
            return [ManagementConnectionResponse(**connection.dict()) for connection in connections]

        finally:
            session.close()

    def get_connection(self, id: int) -> Optional[ManagementConnectionResponse]:
        session = next(self.db.get_session())
        try:
            connection = session.query(ManagementConnection).filter(ManagementConnection.id == id).first()
            if connection:
                return ManagementConnectionResponse(**connection.dict())
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
                target_ip=payload.target_ip
            )
            
            # Lägg till i sessionen
            session.add(mgmt_connection)
            # Commita transaktionen
            session.commit()
            # Refresh för att få det genererade ID:t
            session.refresh(mgmt_connection)
            
            # Returnera som response objekt
            return ManagementConnectionResponse(**mgmt_connection.dict())

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def delete_connection(self, id: int) -> bool:
        session = next(self.db.get_session())
        try:
            connection = session.query(ManagementConnection).filter(ManagementConnection.id == id).first()
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