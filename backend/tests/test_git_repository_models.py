"""The devkit models of a git repository and the table it is stored in describe the same fields."""

from acex.models.git_repository import GitRepositoryRow
from acex_devkit.models.git_repository import GitRepositoryCreate, GitRepositoryResponse, GitRepositoryUpdate


def test_what_is_added_or_changed_is_a_column_of_the_table():
    columns = set(GitRepositoryRow.model_fields)

    assert set(GitRepositoryCreate.model_fields) <= columns
    assert set(GitRepositoryUpdate.model_fields) <= columns


def test_what_is_shown_is_a_column_of_the_table_apart_from_the_config_maps_of_the_process():
    assert set(GitRepositoryResponse.model_fields) - {"config_maps"} <= set(GitRepositoryRow.model_fields)


def test_every_field_of_the_table_that_is_set_by_the_user_can_be_added_and_changed():
    set_by_the_user = {"name", "url", "branch", "path", "auth_method", "credential_id", "username", "ca_certificate"}

    assert set_by_the_user <= set(GitRepositoryCreate.model_fields)
    assert set_by_the_user <= set(GitRepositoryUpdate.model_fields)
