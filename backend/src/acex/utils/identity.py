"""How a serial number or hostname is compared: trimmed and ignoring case, so ``ABC123`` and `` abc123 `` are one.

Kept in one place so the unique indexes, the service lookups and the ZTP matching use the same rule. Python and
SQL agree on spaces and ASCII letters. They differ for tabs, newlines, no-break spaces and non-ASCII capitals,
which only matters for rows stored before the services trimmed values (a CSV import, say): the SQL side does
not strip or lower those, so such a row is not matched by a value that Python has cleaned.
"""

from sqlalchemy import func


def clean(value: str) -> str:
    """The value as it is stored."""
    return value.strip()


def key_of(value: str) -> str:
    """The value as it is compared in Python."""
    return value.strip().lower()


def key_expr(column):
    """The SQL for ``key_of``. A unique index on this makes the database refuse what the services refuse."""
    return func.lower(func.trim(column))
