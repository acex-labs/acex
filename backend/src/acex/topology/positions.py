from datetime import UTC, datetime
from typing import Annotated

from acex.models.topology_position import TopologyPositionRow
from acex_devkit.models.topology import TopologyPosition, TopologyPositionResponse
from fastapi import Query
from sqlmodel import delete, select


class TopologyPositions:
    """The shared layout of the topology page: where people placed items, per container.

    Items nobody placed are laid out by the page. Saving touches only the items sent, so people moving different
    items at the same time keep each other's work.
    """

    def __init__(self, db_manager):
        self.db = db_manager

    def query(self, container: Annotated[list[str] | None, Query()] = None) -> list[TopologyPositionResponse]:
        """The positions in the named containers, or in all of them."""
        session = next(self.db.get_session())
        try:
            statement = select(TopologyPositionRow).order_by(TopologyPositionRow.container, TopologyPositionRow.item)
            if container:
                statement = statement.where(TopologyPositionRow.container.in_(container))
            rows = session.exec(statement).all()
            return [TopologyPositionResponse.model_validate(row, from_attributes=True) for row in rows]
        finally:
            session.close()

    def save(self, positions: list[TopologyPosition], *, updated_by: str) -> list[TopologyPositionResponse]:
        session = next(self.db.get_session())
        try:
            now = datetime.now(UTC)
            rows = []
            for position in {(p.container, p.item): p for p in positions}.values():
                row = session.exec(
                    select(TopologyPositionRow).where(
                        TopologyPositionRow.container == position.container,
                        TopologyPositionRow.item == position.item,
                    )
                ).first() or TopologyPositionRow(container=position.container, item=position.item, x=0, y=0)
                row.x, row.y = position.x, position.y
                row.updated_by, row.updated_at = updated_by, now
                session.add(row)
                rows.append(row)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [TopologyPositionResponse.model_validate(row, from_attributes=True) for row in rows]
        finally:
            session.close()

    def reset(self, container: list[str], item: list[str] | None = None) -> None:
        """Forget the positions in the named containers, or only those of the named items in them.

        The page lays out anew what it has no position for.
        """
        session = next(self.db.get_session())
        try:
            statement = delete(TopologyPositionRow).where(TopologyPositionRow.container.in_(container))
            if item:
                statement = statement.where(TopologyPositionRow.item.in_(item))
            session.exec(statement)
            session.commit()
        finally:
            session.close()
