from .integration_plugin_base import IntegrationPluginBase
from acex.database import DatabaseManager

from typing import get_origin, get_args, Type, Union
from pydantic import BaseModel
from sqlmodel import Session
import sqlite3



class DatabasePlugin(IntegrationPluginBase):
    """
    Init takes a DatabaseManager and the name of the table. If this plugin is used for
    multiple types, multiple instances of this plugin class are used and mounted with separate plugin adaptors.
    """

    def __init__(self, db_manager: DatabaseManager, table: str):
        self.table = table
        self.db = db_manager

    def create(self, data: BaseModel):
        session_gen = self.db.get_session()
        session = next(session_gen)
        try:
            session.add(data)
            session.commit()
            session.refresh(data)
        finally:
            session.close()
        return data

    def get(self, id: str, *args, **kwargs):
        session_gen = self.db.get_session()
        session = next(session_gen)
        try:
            # Anta att tabellens modellklass är tillgänglig via self.table_model
            result = session.get(self.table, id)
            return result
        finally:
            session.close()

    def query(self, filters: dict | None = None, options: list = None) -> list:
        session_gen = self.db.get_session()
        session = next(session_gen)
        try:
            query = session.query(self.table)
            if options:
                for opt in options:
                    query = query.options(opt)
            if filters:
                joined_tables = set()
                for key, value in filters.items():
                    if "." in key:
                        rel_name, col_name = key.split(".", 1)
                        rel_prop = getattr(self.table, rel_name).property
                        related_table = rel_prop.mapper.class_
                        if related_table not in joined_tables:
                            query = query.join(related_table)
                            joined_tables.add(related_table)
                        col = getattr(related_table, col_name)
                        query = query.filter(col.ilike(value) if isinstance(value, str) else col == value)
                    else:
                        col = getattr(self.table, key)
                        query = query.filter(col.ilike(value) if isinstance(value, str) else col == value)
            return query.all()
        finally:
            session.close()

    def update(self, id: str, data):
        session_gen = self.db.get_session()
        session = next(session_gen)
        try:
            obj = session.get(self.table, id)
            print(obj)
            if not obj:
                return None
            # Konvertera till dict om det är en modellinstans
            if hasattr(data, 'model_dump'):
                data_dict = data.model_dump(exclude_unset=True)
            elif hasattr(data, 'dict'):
                data_dict = data.dict(exclude_unset=True)
            else:
                data_dict = data
            for key, value in data_dict.items():
                setattr(obj, key, value)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj
        finally:
            session.close()

    def delete(self, id: str):
        session_gen = self.db.get_session()
        session = next(session_gen)
        try:
            obj = session.get(self.table, id)
            if not obj:
                return False
            session.delete(obj)
            session.commit()
            return True
        finally:
            session.close()