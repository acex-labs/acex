from acex.database import DatabaseManager
from pydantic import BaseModel

from .integration_plugin_base import IntegrationPluginBase


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

    def query(
        self,
        filters: dict | None = None,
        options: list = None,
        extra_filters: list = None,
        limit: int = 100,
        offset: int = 0,
        sort: str | None = None,
        order: str = "asc",
    ) -> list:
        session_gen = self.db.get_session()
        session = next(session_gen)
        try:
            query = session.query(self.table)
            if options:
                for opt in options:
                    query = query.options(opt)
            joined_tables = set()
            if filters:
                for key, value in filters.items():
                    if "." in key:
                        rel_name, col_name = key.split(".", 1)
                        rel_prop = getattr(self.table, rel_name).property
                        related_table = rel_prop.mapper.class_
                        if related_table not in joined_tables:
                            query = query.join(related_table)
                            joined_tables.add(related_table)
                        col = getattr(related_table, col_name)
                        if isinstance(value, list):
                            query = query.filter(col.in_(value))
                        elif isinstance(value, str):
                            query = query.filter(col.ilike(f"%{value}%"))
                        else:
                            query = query.filter(col == value)
                    else:
                        col = getattr(self.table, key)
                        if isinstance(value, list):
                            query = query.filter(col.in_(value))
                        elif isinstance(value, str):
                            query = query.filter(col.ilike(f"%{value}%"))
                        else:
                            query = query.filter(col == value)
            if extra_filters:
                for f in extra_filters:
                    query = query.filter(f)
            total = query.count()
            if sort:
                if "." in sort:
                    rel_name, col_name = sort.split(".", 1)
                    rel_prop = getattr(self.table, rel_name).property
                    related_table = rel_prop.mapper.class_
                    if related_table not in joined_tables:
                        query = query.join(related_table)
                        joined_tables.add(related_table)
                    sort_col = getattr(related_table, col_name)
                else:
                    sort_col = getattr(self.table, sort)
                query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
                # tiebreaker for stable pagination
                pk_col = getattr(self.table, "id", None)
                if pk_col is not None and sort != "id":
                    query = query.order_by(pk_col)
            items = query.offset(offset).limit(limit).all()
            return {"items": items, "total": total}
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
            if hasattr(data, "model_dump"):
                data_dict = data.model_dump(exclude_unset=True)
            elif hasattr(data, "dict"):
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
