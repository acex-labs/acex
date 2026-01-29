from rich.table import Table
from rich.console import Console

console = Console()


def print_object(obj, title=None, pydantic_class=None):
    if hasattr(obj, "dict"):
        obj = obj.dict()
    if pydantic_class is not None:
        fields = list(pydantic_class.model_fields.keys())
    else:
        fields = list(obj.keys())
    table = Table(title=title)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="white")
    for field in fields:
        value = obj.get(field, "")
        if isinstance(value, dict) and not value:
            value = "-"
        elif isinstance(value, dict):
            import json
            value = json.dumps(value, indent=2)
        table.add_row(field, str(value))
    console.print(table)

def print_list_table(data, columns=None, title=None, pydantic_class=None):
    """
    Print a list of dicts or Pydantic objects as a table.
    :param data: List of dicts or Pydantic objects
    :param columns: List of column names (keys in dict). If None and pydantic_class is given, use its fields.
    :param title: Optional table title
    :param pydantic_class: Optional Pydantic class to get fields from
    """
    if pydantic_class is not None and columns is None:
        columns = list(pydantic_class.model_fields.keys())
    table = Table(title=title)
    for col in columns:
        table.add_column(col)
    for row in data:
        if hasattr(row, "dict"):
            row = row.dict()
        table.add_row(*(str(row.get(col, "")) for col in columns))
    console.print(table)

