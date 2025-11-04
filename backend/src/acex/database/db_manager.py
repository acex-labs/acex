

from sqlmodel import SQLModel
from acex.database import Connection

from acex.models import system_models

class DatabaseManager:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create_tables(self):
        SQLModel.metadata.create_all(self.connection.engine)

    def drop_tables(self):
        SQLModel.metadata.drop_all(self.connection.engine)

    def get_session(self):
        return self.connection.get_session()