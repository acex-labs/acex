from .integration_plugin_base import IntegrationPluginBase
from acex.models import (Asset, LogicalNode, Node, Ned)

from typing import get_origin, get_args, Type, Union
from pydantic import BaseModel
import sqlite3


class Sqlite(): 
    def __init__(self, filepath: str):
        """
        Sqlite datasource plugin for ACE.
        Initializes a connection to a SQLite database file.
        This is just a factory class that will create a SqlitePluginInstance for each model used.
        """
        self.filepath = filepath

    def create_plugin(self, model: Type[BaseModel]) -> 'SqlitePlugin':
        """
        Create a plugin instance for a specific model.
        :param model: The Pydantic model class to use for the plugin.
        :return: An instance of SqlitePlugin.
        """
        return SqlitePlugin(filepath=self.filepath, model=model)


class SqlitePlugin(IntegrationPluginBase): 

    def __init__(self, filepath: str, model: Type[BaseModel]):
        self.model = model
        self.table = f"{model.__name__.lower()}s"
        self.filepath = filepath

    def init_table(self, model, table_name: str):
        """
        Initializes a table, takes a model(pydantic class) as
        input and creates table with correct column types 
        based on the typing of the model class.

        TODO: inte stöd för nestade pydanticklasser/join...
        """
        conn = sqlite3.connect(self.filepath)
        cursor = conn.cursor()

        
        print(f"skapa tabell '{table_name}' för {model}")

        columns = []

        if "id" not in model.model_fields:
            columns.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
        for k,v in model.model_fields.items():
            name = k
            _type = v.annotation

            nullable = False  # antas NOT NULL om inte Optional
            # Get the type from Union/Optional definitions
            if get_origin(_type) is Union and type(None) in get_args(_type):
                # Is optional:
                nullable = True
                args = get_args(_type)
                non_none_types = [t for t in args if t is not type(None)]
                base_type = non_none_types[0] if non_none_types else None
                _type = base_type

            # Mappa Python-typer till SQLite-typer
            if _type == int:
                sql_type = "INTEGER"
            elif _type == float:
                sql_type = "REAL"
            elif _type == str:
                sql_type = "TEXT"
            elif _type == bool:
                sql_type = "INTEGER"  # SQLite saknar BOOLEAN, brukar använda 0/1
            else:
                sql_type = "TEXT"  # fallback

            null_str = "" if not nullable else "NULL"
            columns.append(f"{name} {sql_type} {null_str}".strip())

        columns_str = ", ".join(columns)
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_str});"
        cursor.execute(sql)
        conn.commit()
        conn.close()


    def create(self, data: BaseModel): 
        data_dict = data.model_dump()

        conn = sqlite3.connect(self.filepath)
        cursor = conn.cursor()

        # Hämta nästa lediga radnummer
        count_query = f"SELECT COUNT(*) as count FROM {self.table}"
        cursor.execute(count_query)
        count_result = cursor.fetchone()
        next_row_id = count_result[0] + 1

        # Ta bort id från data för insertion
        insert_data = {k: v for k, v in data_dict.items()}
        insert_data["id"] = next_row_id

        # Konvertera bool till int (SQLite saknar bool)
        for k, v in insert_data.items():
            if isinstance(v, bool):
                insert_data[k] = int(v)

        columns = ", ".join(insert_data.keys())
        placeholders = ", ".join(["?"] * len(insert_data))
        values = list(insert_data.values())

        sql = f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, values)

        conn.commit()
        conn.close()

        # Returnera objektet med radnummer som ID
        return self.model(**data_dict)


    def get(self, id: str): 
        conn = sqlite3.connect(self.filepath)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            data = cursor.execute(f"SELECT * FROM {self.table} WHERE id = ?", (id,))
            row = data.fetchone()
            if row is not None:
                row_dict = dict(row)  # Konvertera till dict
                return self.model(**row_dict)
            else:
                print("Ingen rad hittades.")
                return None
        finally:
            conn.close()

    def query(self, filters: dict|None = None) -> list:
        conn = sqlite3.connect(self.filepath)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        data = cursor.execute(f"SELECT * from {self.table}")
        rows = data.fetchall()
        result = []
        for i, row in enumerate(rows, start=1):
            d = dict()
            d["id"] = i  # radnummer som artificiellt id
            d.update(row)
            result.append(self.model(**d))

        conn.close()

        return result

    def update(self, id: str, data: dict):
        data = data.model_dump()
        """Uppdatera en rad med givet id med data (dict)."""
        conn = sqlite3.connect(self.filepath)
        cursor = conn.cursor()
        # Ta bort id ur data om det finns
        data = {k: v for k, v in data.items() if k != "id"}
        # Konvertera bool till int
        for k, v in data.items():
            if isinstance(v, bool):
                data[k] = int(v)
        if not data:
            conn.close()
            return False
        columns = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(id)
        sql = f"UPDATE {self.table} SET {columns} WHERE id = ?"
        cursor.execute(sql, values)
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def delete(self, id: str):
        """Ta bort en rad med givet id."""
        conn = sqlite3.connect(self.filepath)
        cursor = conn.cursor()
        sql = f"DELETE FROM {self.table} WHERE id = ?"
        cursor.execute(sql, (id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted