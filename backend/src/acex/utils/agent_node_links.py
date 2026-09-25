"""Declarative explicit-node membership shared by telemetry and collection agents."""

from acex.models.node import Node
from acex_devkit.models.agent_manifest import AgentNodeSetResult
from fastapi import HTTPException
from sqlalchemy import func, update
from sqlmodel import delete, select


def set_agent_nodes(
    session,
    *,
    agent_model,
    link_model,
    agent_fk: str,
    agent_id: int,
    node_ids: list[int],
    expected_revision: int | None = None,
) -> AgentNodeSetResult:
    """Make the agent's explicit node links exactly `node_ids`, atomically.

    - 404 if the agent does not exist; 422 (nothing changed) on unknown node ids.
    - 409 if `expected_revision` differs from the current revision, or if the
      revision moved between read and write (concurrent edit).
    - The revision is bumped once, and only when the set actually changes.
    """
    agent = session.get(agent_model, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"{agent_model.__name__} not found")
    current_revision = agent.config_revision or 0
    if expected_revision is not None and expected_revision != current_revision:
        raise HTTPException(
            status_code=409,
            detail=f"Agent changed (revision {current_revision}, expected {expected_revision}); reload and retry",
        )

    wanted = set(node_ids)
    if wanted:
        known = set(session.exec(select(Node.id).where(Node.id.in_(wanted))).all())
        unknown = sorted(wanted - known)
        if unknown:
            raise HTTPException(status_code=422, detail={"message": "Unknown node ids", "node_ids": unknown})

    fk = getattr(link_model, agent_fk)
    current = set(session.exec(select(link_model.node_id).where(fk == agent_id)).all())
    added = sorted(wanted - current)
    removed = sorted(current - wanted)
    if not added and not removed:
        return AgentNodeSetResult(config_revision=current_revision)

    # Compare-and-set on the revision so two concurrent PUTs cannot both win.
    bumped = session.exec(
        update(agent_model)
        .where(agent_model.id == agent_id, func.coalesce(agent_model.config_revision, 0) == current_revision)
        .values(config_revision=current_revision + 1)
    )
    if bumped.rowcount != 1:
        session.rollback()
        raise HTTPException(status_code=409, detail="Agent changed concurrently; reload and retry")

    if removed:
        session.exec(delete(link_model).where(fk == agent_id, link_model.node_id.in_(removed)))
    for node_id in added:
        session.add(link_model(**{agent_fk: agent_id, "node_id": node_id}))
    session.commit()
    return AgentNodeSetResult(added=added, removed=removed, config_revision=current_revision + 1)
