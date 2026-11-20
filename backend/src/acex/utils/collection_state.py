from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal

from acex.models.collection_agent import CollectionAgent
from acex.models.collection_state import NodeCollectionState
from acex.models.node import Node
from acex_devkit.models.collection_state import (
    MESSAGE_LENGTH,
    AgentCollectionSummary,
    CollectionFailure,
    CollectionResult,
    CollectionStatus,
    NodeCollectionStateResponse,
)
from sqlmodel import func, select


def _state(session, node_id: int) -> NodeCollectionState:
    return session.get(NodeCollectionState, node_id) or NodeCollectionState(node_id=node_id)


def record_success(session, node_id: int, now: datetime | None = None, agent_id: int | None = None) -> None:
    # An upload does not say which agent made it, so without `agent_id` the agent that reported last stays.
    now = now or datetime.now(UTC)
    state = _state(session, node_id)
    state.last_attempt_at = now
    state.last_success_at = now
    state.failing_since = None
    state.consecutive_failures = 0
    state.category = None
    state.message = None
    if agent_id is not None:
        state.agent_id = agent_id
    session.add(state)


def record_failure(
    session,
    node_id: int,
    category: CollectionFailure | None,
    message: str | None,
    now: datetime | None = None,
    agent_id: int | None = None,
) -> None:
    now = now or datetime.now(UTC)
    state = _state(session, node_id)
    state.last_attempt_at = now
    if not state.consecutive_failures or state.failing_since is None:
        state.failing_since = now
    state.consecutive_failures = (state.consecutive_failures or 0) + 1
    state.category = str(category or CollectionFailure.other)
    state.message = message[:MESSAGE_LENGTH] if message else None
    if agent_id is not None:
        state.agent_id = agent_id
    session.add(state)


def record(session, result: CollectionResult, now: datetime | None = None, agent_id: int | None = None) -> None:
    if result.ok:
        record_success(session, result.node_id, now, agent_id)
    else:
        record_failure(session, result.node_id, result.category, result.message, now, agent_id)


def to_response(state: NodeCollectionState, agent_name: str | None = None) -> NodeCollectionStateResponse:
    return NodeCollectionStateResponse(
        status=CollectionStatus.failing if state.consecutive_failures else CollectionStatus.ok,
        last_attempt_at=state.last_attempt_at,
        last_success_at=state.last_success_at,
        failing_since=state.failing_since,
        consecutive_failures=state.consecutive_failures or 0,
        category=state.category,
        message=state.message,
        agent_id=state.agent_id,
        agent_name=agent_name,
    )


def states_for(session, node_ids: Iterable[int]) -> dict[int, NodeCollectionStateResponse]:
    ids = list(node_ids)
    if not ids:
        return {}
    rows = session.exec(select(NodeCollectionState).where(NodeCollectionState.node_id.in_(ids))).all()
    agent_ids = {row.agent_id for row in rows if row.agent_id is not None}
    names = {}
    if agent_ids:
        agents = session.exec(select(CollectionAgent.id, CollectionAgent.name).where(CollectionAgent.id.in_(agent_ids)))
        names = dict(agents.all())
    return {row.node_id: to_response(row, names.get(row.agent_id)) for row in rows}


def status_filter(status: Literal["ok", "failing", "unknown"]):
    """A condition on the node list: nodes that fail to be collected, nodes that were collected last time, or
    nodes no agent has reported on yet."""
    reported = select(NodeCollectionState.node_id)
    if status == "failing":
        return Node.id.in_(reported.where(NodeCollectionState.consecutive_failures > 0))
    if status == "ok":
        return Node.id.in_(reported.where(NodeCollectionState.consecutive_failures == 0))
    return Node.id.not_in(reported)


def agent_filter(agent_id: int):
    """A condition on the node list: the nodes whose last attempt this collection agent made."""
    return Node.id.in_(select(NodeCollectionState.node_id).where(NodeCollectionState.agent_id == agent_id))


def summary_for(session, agent_id: int) -> AgentCollectionSummary:
    failing = NodeCollectionState.consecutive_failures > 0
    rows = session.exec(
        select(failing, NodeCollectionState.category, func.count())
        .where(NodeCollectionState.agent_id == agent_id)
        .group_by(failing, NodeCollectionState.category)
    ).all()
    by_category: dict[CollectionFailure, int] = {}
    for is_failing, category, count in rows:
        if is_failing:
            key = CollectionFailure(category or CollectionFailure.other)
            by_category[key] = by_category.get(key, 0) + count
    return AgentCollectionSummary(
        collected=sum(count for is_failing, _, count in rows if not is_failing),
        not_collected=sum(by_category.values()),
        by_category=by_category,
    )
