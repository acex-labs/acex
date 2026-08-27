from acex.database import Connection
from sqlmodel import SQLModel


class DatabaseManager:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create_tables(self):
        SQLModel.metadata.create_all(self.connection.engine)

    def drop_tables(self):
        SQLModel.metadata.drop_all(self.connection.engine)

    def get_session(self):
        return self.connection.get_session()

    def upgrade(self, revision: str = "head"):
        """Apply Alembic migrations up to `revision`, reusing this manager's live DB connection."""
        from pathlib import Path

        from alembic import command
        from alembic.config import Config

        alembic_ini = Path(__file__).resolve().parents[3] / "alembic.ini"
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.attributes["connection"] = self.connection.engine
        command.upgrade(alembic_cfg, revision)
