"""The models of a git repository that ConfigMaps are read from: what may be added, and how it is shown."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from acex_devkit.models.git_repository import (
    GIT_AUTH_CREDENTIAL_TYPES,
    GitAuthMethod,
    GitRepositoryCreate,
    GitRepositoryResponse,
    GitRepositoryUpdate,
)
from pydantic import ValidationError

URL = "https://git.example.com/team/maps.git"
PEM = "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----"


def test_a_repository_needs_only_a_name_and_a_url_and_signs_in_with_a_token_by_default():
    repository = GitRepositoryCreate(name="maps", url=URL)

    assert repository.auth_method is GitAuthMethod.HTTPS_TOKEN
    assert (repository.branch, repository.path, repository.enabled) == ("main", "", True)
    assert (repository.credential_id, repository.username, repository.ca_certificate) == (None, None, None)


def test_every_method_says_which_credential_it_needs():
    assert set(GIT_AUTH_CREDENTIAL_TYPES) == set(GitAuthMethod)
    assert GIT_AUTH_CREDENTIAL_TYPES[GitAuthMethod.HTTPS_ANONYMOUS] is None
    assert GIT_AUTH_CREDENTIAL_TYPES[GitAuthMethod.HTTPS_TOKEN] == "token"


def test_a_method_is_stored_and_sent_as_its_name():
    assert GitRepositoryCreate(name="m", url=URL, auth_method="https_anonymous").auth_method is (
        GitAuthMethod.HTTPS_ANONYMOUS
    )
    assert GitRepositoryCreate(name="m", url=URL).model_dump(mode="json")["auth_method"] == "https_token"
    with pytest.raises(ValidationError):
        GitRepositoryCreate(name="m", url=URL, auth_method="ssh_key")


@pytest.mark.parametrize(
    "url",
    [
        "http://git.example.com/maps.git",
        "git@git.example.com:team/maps.git",
        "ssh://git@git.example.com/maps.git",
        "file:///srv/maps.git",
        "/srv/maps.git",
        "https://",
        "",
    ],
)
def test_only_an_https_url_is_accepted(url):
    with pytest.raises(ValidationError, match="https"):
        GitRepositoryCreate(name="maps", url=url)
    with pytest.raises(ValidationError, match="https"):
        GitRepositoryUpdate(url=url)


@pytest.mark.parametrize("url", ["https://user:secret@git.example.com/maps.git", "https://token@git.example.com/m.git"])
def test_a_url_does_not_hold_a_secret(url):
    with pytest.raises(ValidationError, match="credential"):
        GitRepositoryCreate(name="maps", url=url)


def test_a_url_keeps_its_port_and_loses_surrounding_blanks():
    assert GitRepositoryCreate(name="m", url="  https://git.example.com:8443/m.git\n").url == (
        "https://git.example.com:8443/m.git"
    )


@pytest.mark.parametrize(
    ("given", "kept"),
    [("", ""), (".", ""), ("config_maps", "config_maps"), ("config_maps/", "config_maps"), ("./a//b/", "a/b")],
)
def test_the_directory_of_the_config_maps_is_a_path_in_the_repository(given, kept):
    assert GitRepositoryCreate(name="m", url=URL, path=given).path == kept
    assert GitRepositoryUpdate(path=given).path == kept


@pytest.mark.parametrize("path", ["..", "../maps", "a/../../b", "/etc", "/"])
def test_the_directory_cannot_leave_the_repository(path):
    with pytest.raises(ValidationError, match="in the repository"):
        GitRepositoryCreate(name="m", url=URL, path=path)
    with pytest.raises(ValidationError, match="in the repository"):
        GitRepositoryUpdate(path=path)


def test_a_ca_certificate_is_pem_or_nothing():
    assert GitRepositoryCreate(name="m", url=URL, ca_certificate=PEM).ca_certificate == PEM
    assert GitRepositoryCreate(name="m", url=URL, ca_certificate=None).ca_certificate is None
    assert GitRepositoryUpdate(ca_certificate="").ca_certificate == ""
    with pytest.raises(ValidationError, match="PEM"):
        GitRepositoryCreate(name="m", url=URL, ca_certificate="not a certificate")
    with pytest.raises(ValidationError, match="PEM"):
        GitRepositoryUpdate(ca_certificate="not a certificate")


def test_a_name_and_a_branch_are_not_empty():
    with pytest.raises(ValidationError):
        GitRepositoryCreate(name="", url=URL)
    with pytest.raises(ValidationError):
        GitRepositoryCreate(name="m", url=URL, branch="")
    with pytest.raises(ValidationError):
        GitRepositoryUpdate(name="")


def test_an_update_says_which_fields_were_sent_so_a_credential_can_be_cleared():
    sent_null = GitRepositoryUpdate(credential_id=None)
    sent_nothing = GitRepositoryUpdate()

    assert sent_null.model_fields_set == {"credential_id"}
    assert sent_null.model_dump(mode="json", include=sent_null.model_fields_set) == {"credential_id": None}
    assert sent_nothing.model_fields_set == set()
    assert GitRepositoryUpdate(url=URL, auth_method="https_anonymous").model_dump(
        mode="json", include={"auth_method"}
    ) == {"auth_method": "https_anonymous"}


def test_a_repository_is_shown_from_what_is_stored_with_the_config_maps_of_the_process():
    now = datetime.now(UTC)
    stored = SimpleNamespace(
        id=3,
        name="maps",
        url=URL,
        branch="main",
        path="config_maps",
        auth_method="https_token",
        credential_id=7,
        username=None,
        ca_certificate=None,
        enabled=True,
        commit="a" * 40,
        last_checked_at=now,
        last_synced_at=now,
        last_error=None,
        created_by="admin",
        updated_by="admin",
        created_at=now,
        updated_at=now,
    )

    shown = GitRepositoryResponse.model_validate(stored)
    assert (shown.id, shown.auth_method, shown.config_maps) == (3, GitAuthMethod.HTTPS_TOKEN, [])

    shown.config_maps = ["a.py:alpha"]
    assert shown.model_dump(mode="json")["config_maps"] == ["a.py:alpha"]
    assert shown.model_dump(mode="json")["auth_method"] == "https_token"
