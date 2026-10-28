"""Agents report the version of their package, the commit of their image and the branch it was built on in every ack,
and the API returns them."""

import pytest
from acex.inventory.collection_agent_manager import CollectionAgentManager
from acex.observability.agents.manager import TelemetryAgentManager
from acex_devkit.models.collection_agent import CollectionAgentAck, CollectionAgentCreate
from acex_devkit.models.telemetry_agent import TelemetryAgentAck, TelemetryAgentCreate
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


BUILD = "7f67e1d8e0eb3e23460e85f72d4c12550b0ea1d9"
REF = "dev"


@pytest.fixture(params=["collection", "telemetry"])
def agents(request):
    """The same four expectations for both kinds of agent: (create, ack, get)."""
    if request.param == "collection":
        manager = CollectionAgentManager(_Db())
        return (
            lambda: manager.create(CollectionAgentCreate(name="stage")),
            lambda id, **reported: manager.ack_manifest(id, CollectionAgentAck(config_revision=3, **reported)),
            manager.get,
        )
    manager = TelemetryAgentManager(_Db())
    return (
        lambda: manager.create(TelemetryAgentCreate(name="stage")),
        lambda id, **reported: manager.ack(id, TelemetryAgentAck(config_revision=3, **reported)),
        manager.get,
    )


def test_a_new_agent_has_not_reported_anything(agents):
    create, _, get = agents
    agent = get(create().id)
    assert agent.agent_version is None
    assert agent.build_id is None
    assert agent.build_ref is None


def test_an_ack_stores_the_version_the_build_and_the_branch(agents):
    create, ack, get = agents
    id = create().id
    result = ack(id, agent_version="0.16.0", build_id=BUILD, build_ref=REF)
    assert result.acked_revision == 3
    agent = get(id)
    assert (agent.agent_version, agent.build_id, agent.build_ref) == ("0.16.0", BUILD, REF)
    assert agent.acked_revision == 3


def test_an_ack_without_them_clears_what_an_earlier_ack_reported(agents):
    """An agent rolled back to a version that does not report must not keep showing the newer one."""
    create, ack, get = agents
    id = create().id
    ack(id, agent_version="0.16.0", build_id=BUILD, build_ref=REF)
    ack(id)
    agent = get(id)
    assert agent.agent_version is None
    assert agent.build_id is None
    assert agent.build_ref is None


def test_an_ack_with_only_a_version_is_accepted(agents):
    create, ack, get = agents
    id = create().id
    ack(id, agent_version="0.8.0")
    agent = get(id)
    assert (agent.agent_version, agent.build_id, agent.build_ref) == ("0.8.0", None, None)


def test_an_ack_for_an_unknown_agent_is_a_404(agents):
    _, ack, _ = agents
    with pytest.raises(HTTPException) as error:
        ack(999, agent_version="0.16.0", build_id=BUILD, build_ref=REF)
    assert error.value.status_code == 404
