import warnings

import pytest
from acex.credentials.credential_manager import CredentialManager
from acex.models.credential import CredentialCreate, CredentialUpdate, NodeCredentialCreate, SiteCredentialCreate
from cryptography.fernet import Fernet
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


@pytest.fixture(autouse=True)
def deprecations_are_errors():
    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=DeprecationWarning, module=r"acex\.credentials")
        yield


@pytest.fixture
def manager():
    return CredentialManager(_Db(), Fernet.generate_key().decode())


def community(manager, name="snmp-ro", value="public"):
    return manager.create(CredentialCreate(name=name, credential_type="snmp_community", fields={"community": value}))


def ssh_key(manager, name="ops-key"):
    return manager.create(
        CredentialCreate(name=name, credential_type="ssh_key", fields={"username": "ops", "private_key": "key"})
    )


def test_a_created_credential_can_be_fetched(manager):
    created = manager.create(
        CredentialCreate(name="lab-login", credential_type="userpass", fields={"username": "admin", "password": "pw"})
    )

    fetched = manager.get(created.id)

    assert fetched.name == "lab-login"
    assert {f.field_name: f.field_value for f in fetched.fields} == {"username": "admin", "password": None}
    assert manager.get_secret(created.id).fields == {"username": "admin", "password": "pw"}


def test_a_missing_credential_is_a_404(manager):
    with pytest.raises(HTTPException) as error:
        manager.get(99)

    assert error.value.status_code == 404


def test_credentials_are_listed_by_name_prefix(manager):
    for name in ("beta", "alpha", "alps"):
        community(manager, name=name)

    assert [c.name for c in manager.query()] == ["alpha", "alps", "beta"]
    assert [c.name for c in manager.query(name="AL")] == ["alpha", "alps"]


def test_updating_the_fields_replaces_the_old_ones(manager):
    created = community(manager, value="old")

    manager.update(created.id, CredentialUpdate(fields={"community": "new"}))

    assert manager.get_secret(created.id).fields == {"community": "new"}


def test_updating_without_fields_keeps_the_stored_ones(manager):
    created = community(manager, value="kept")

    renamed = manager.update(created.id, CredentialUpdate(name="renamed"))

    assert renamed.name == "renamed"
    assert [f.field_name for f in renamed.fields] == ["community"]
    assert manager.get_secret(created.id).fields == {"community": "kept"}


def test_deleting_a_credential_removes_its_fields_and_assignments(manager):
    created = community(manager)
    manager.assign_to_node(1, NodeCredentialCreate(credential_id=created.id))
    manager.assign_to_site("lab", SiteCredentialCreate(credential_id=created.id))

    manager.delete(created.id)

    assert manager.list_node_credentials(1) == []
    assert manager.list_site_credentials("lab") == []
    assert manager.query() == []


def test_a_credential_is_assigned_to_a_node_once(manager):
    created = community(manager)

    link = manager.assign_to_node(1, NodeCredentialCreate(credential_id=created.id))
    with pytest.raises(HTTPException) as error:
        manager.assign_to_node(1, NodeCredentialCreate(credential_id=created.id))

    assert (link.node_id, link.credential_name, link.credential_type) == (1, "snmp-ro", "snmp_community")
    assert error.value.status_code == 409
    assert [x.id for x in manager.list_node_credentials(1)] == [link.id]
    assert manager.list_node_credentials(2) == []


def test_a_credential_is_assigned_to_a_site_once(manager):
    created = community(manager)

    link = manager.assign_to_site("lab", SiteCredentialCreate(credential_id=created.id))
    with pytest.raises(HTTPException) as error:
        manager.assign_to_site("lab", SiteCredentialCreate(credential_id=created.id))

    assert (link.site_name, link.credential_name) == ("lab", "snmp-ro")
    assert error.value.status_code == 409
    assert [x.id for x in manager.list_site_credentials("lab")] == [link.id]
    assert manager.list_site_credentials("other") == []


def test_assigning_a_missing_credential_is_a_404(manager):
    with pytest.raises(HTTPException) as error:
        manager.assign_to_node(1, NodeCredentialCreate(credential_id=99))

    assert error.value.status_code == 404


def test_an_assignment_can_be_removed_once(manager):
    created = community(manager)
    manager.assign_to_node(1, NodeCredentialCreate(credential_id=created.id))
    manager.assign_to_site("lab", SiteCredentialCreate(credential_id=created.id))

    manager.remove_node_credential(1, created.id)
    manager.remove_site_credential("lab", created.id)

    assert manager.list_node_credentials(1) == []
    assert manager.list_site_credentials("lab") == []
    for remove in (
        lambda: manager.remove_node_credential(1, created.id),
        lambda: manager.remove_site_credential("lab", created.id),
    ):
        with pytest.raises(HTTPException) as error:
            remove()
        assert error.value.status_code == 404


def test_the_manifest_maps_each_node_to_its_credentials(manager):
    snmp = community(manager)
    key = ssh_key(manager)
    manager.assign_to_node(1, NodeCredentialCreate(credential_id=snmp.id))
    manager.assign_to_node(1, NodeCredentialCreate(credential_id=key.id))
    manager.assign_to_node(2, NodeCredentialCreate(credential_id=snmp.id))
    manager.assign_to_node(3, NodeCredentialCreate(credential_id=key.id))

    assert manager.get_node_credentials_for_manifest([1, 2]) == {
        1: {"snmp_community": snmp.id, "ssh_key": key.id},
        2: {"snmp_community": snmp.id},
    }


def test_the_snmp_community_comes_from_the_node_then_the_site_then_the_default(manager):
    node_value = community(manager, name="node-community", value="node-secret")
    site_value = community(manager, name="site-community", value="site-secret")
    manager.assign_to_site("lab", SiteCredentialCreate(credential_id=site_value.id))

    assert manager.get_node_community(1) is None
    assert manager.get_site_community("lab") == "site-secret"
    assert manager.get_site_community("other") == "public"
    assert manager.resolve_snmp_community_source(1, "lab") == "site"
    assert manager.resolve_snmp_community_source(1, "other") == "default"
    assert manager.resolve_snmp_community_source(1) == "default"

    manager.assign_to_node(1, NodeCredentialCreate(credential_id=node_value.id))

    assert manager.get_node_community(1) == "node-secret"
    assert manager.resolve_snmp_community_source(1, "lab") == "node"
    assert manager.resolve_snmp_community_source(2, "lab") == "site"


def test_only_snmp_community_credentials_resolve_the_community(manager):
    key = ssh_key(manager)
    manager.assign_to_node(1, NodeCredentialCreate(credential_id=key.id))
    manager.assign_to_site("lab", SiteCredentialCreate(credential_id=key.id))

    assert manager.get_node_community(1) is None
    assert manager.get_site_community("lab") == "public"
    assert manager.resolve_snmp_community_source(1, "lab") == "default"
