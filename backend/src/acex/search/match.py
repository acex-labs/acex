from sqlalchemy import String, cast, or_

# A Postgres integer holds at most ten digits and the largest nine-digit number always fits. A longer
# number is not an id, and comparing it to an id column would be refused by the database.
MAX_ID_DIGITS = 9


def id_match(text: str, id_column):
    """The condition that a row has the id the text spells, or None when the text is not a number."""
    if text.isascii() and text.isdigit() and len(text) <= MAX_ID_DIGITS:
        return id_column == int(text)
    return None


def quick_match(text: str, columns, id_column=None):
    """The condition a list's ``q`` puts on its rows: any of the columns contains the text.

    Matching ignores case. A typed ``%`` or ``_`` is that character, not a wildcard (autoescape).
    Each column is cast to text, so an enum column (an asset's vendor) or a number matches on
    every database, SQLite included.

    With ``id_column``, a text made only of digits also matches the row with that id, so the number
    shown as an ID in a list can be typed into the same box.
    """
    conditions = [cast(column, String).icontains(text, autoescape=True) for column in columns]
    by_id = id_match(text, id_column) if id_column is not None else None
    if by_id is not None:
        conditions.append(by_id)
    return or_(*conditions)
