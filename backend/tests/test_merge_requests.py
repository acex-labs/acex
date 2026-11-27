import json
import logging
from urllib.parse import parse_qs, quote, unquote, urlsplit

import httpx
import pytest
from acex.api import auth
from acex.compilers.config_compiler import ConfigCompiler
from acex.credentials.credential_manager import CredentialManager
from acex.git_sync import Git, GitHostError, GitRepositoryConflict, GitSyncManager
from acex.git_sync import gitlab as gitlab_api
from acex.settings import GitSyncSettings
from acex_devkit.models.credential import CredentialCreate
from acex_devkit.models.git_repository import GitRepositoryCreate, GitRepositoryUpdate, MergeRequestCreate
from cryptography.fernet import Fernet
from test_git_sync import _client, _Db, _internal_ca_host

TOKEN = "s3cret-merge-request-token"
URL = "https://gitlab.example.com/net/config-maps.git"
ANNA = {"Authorization": "Bearer anna"}

NTP = """from acex.config_map import ConfigMap


class Ntp(ConfigMap):
    def compile(self, context):
        pass


ntp = Ntp()
"""


class _FakeGitLab:
    """GitLab's answers for one project, as far as a merge request needs them. Keeps what it was sent."""

    def __init__(self, project="net/config-maps", token=TOKEN, page_size=100):
        self.project = project
        self.token = token
        self.page_size = page_size
        self.branches = {"main": {"README.md": "# maps\n", "got/ntp.py": NTP, "sto/vlan.py": NTP}}
        self.commits = []
        self.merge_requests = []
        self.requests = []
        #: Answers to give instead of the usual one, by what is asked for: "tree", "files", "commits",
        #: "merge_requests" or "branches".
        self.instead = {}

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def sent(self, method: str, what: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == method and f"/{what}" in r.url.raw_path.decode()]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("private-token") != self.token:
            return httpx.Response(401, json={"message": "401 Unauthorized"})
        raw = urlsplit(request.url.raw_path.decode())
        root = f"/api/v4/projects/{quote(self.project, safe='')}/"
        if not raw.path.startswith(root):
            return httpx.Response(404, json={"message": "404 Project Not Found"})
        asked = raw.path.removeprefix(root).removeprefix("repository/")
        what, _, rest = asked.partition("/")
        if what in self.instead:
            return self.instead[what]
        query = {name: values[0] for name, values in parse_qs(raw.query).items()}
        return getattr(self, f"_{what}")(request, unquote(rest), query)

    def _tree(self, request, _, query):
        files = self.branches.get(query["ref"])
        if files is None:
            return httpx.Response(404, json={"message": "404 Tree Not Found"})
        directories = {"/".join(path.split("/")[:depth]) for path in files for depth in range(1, path.count("/") + 1)}
        entries = sorted([(d, "tree") for d in directories] + [(f, "blob") for f in files])
        start = int(query.get("page_token", 0))
        page = [{"path": path, "name": path.rsplit("/", 1)[-1], "type": kind} for path, kind in entries]
        headers = {}
        if start + self.page_size < len(entries):
            following = request.url.copy_merge_params({"page_token": str(start + self.page_size)})
            headers["link"] = f'<{following}>; rel="next"'
        return httpx.Response(200, json=page[start : start + self.page_size], headers=headers)

    def _files(self, request, path, query):
        return httpx.Response(200 if path in self.branches.get(query["ref"], {}) else 404)

    def _commits(self, request, _, query):
        body = json.loads(request.content)
        if body["branch"] in self.branches:
            return httpx.Response(400, json={"message": f"A branch called '{body['branch']}' already exists."})
        if body["start_branch"] not in self.branches:
            return httpx.Response(400, json={"message": "You can only create or edit files when you are on a branch"})
        files = dict(self.branches[body["start_branch"]])
        for action in body["actions"]:
            if (action["action"] == "create") == (action["file_path"] in files):
                exists = "already exists" if action["action"] == "create" else "doesn't exist"
                return httpx.Response(400, json={"message": f"A file with this name {exists}"})
            files[action["file_path"]] = action["content"]
        self.branches[body["branch"]] = files
        self.commits.append(body)
        return httpx.Response(201, json={"id": "c0ffee"})

    def _merge_requests(self, request, _, query):
        body = json.loads(request.content)
        self.merge_requests.append(body)
        number = len(self.merge_requests)
        url = f"https://gitlab.example.com/{self.project}/-/merge_requests/{number}"
        return httpx.Response(201, json={"iid": number, "id": 4000 + number, "web_url": url})

    def _branches(self, request, name, query):
        self.branches.pop(name, None)
        return httpx.Response(204)


@pytest.fixture
def gitlab():
    return _FakeGitLab()


@pytest.fixture
def env(tmp_path, gitlab):
    db = _Db()
    credentials = CredentialManager(db, Fernet.generate_key().decode())
    manager = GitSyncManager(
        db,
        ConfigCompiler(db),
        credentials,
        GitSyncSettings(checkout_dir=str(tmp_path / "checkouts")),
        # git may not leave the machine here: the sync of an added repository fails at once and is not what is tested.
        git=Git(allowed_protocols=("file",)),
        http_transport=gitlab.transport(),
    )
    return manager, credentials


def repository(env, name="maps", url=URL, token=TOKEN, **fields):
    manager, credentials = env
    credential = credentials.create(
        CredentialCreate(name=f"{name}-merge-requests", credential_type="token", fields={"token": token})
    )
    payload = GitRepositoryCreate(
        name=name, url=url, auth_method="https_anonymous", merge_request_credential_id=credential.id, **fields
    )
    return manager.create(payload, created_by="admin")


def send(client, repo, **fields):
    body = {"path": "got/banner.py", "content": NTP, "title": "Add the banner of got", **fields}
    return client.post(f"/api/v1/git_repositories/{repo.id}/merge_requests", json=body, headers=ANNA)


def test_a_file_is_sent_as_a_merge_request_into_the_branch_the_repository_follows(env, gitlab, monkeypatch):
    repo = repository(env)

    response = send(_client(env, monkeypatch), repo, description="NTP as it runs on the core switch.")

    assert response.status_code == 201
    sent = response.json()
    assert sent["url"] == "https://gitlab.example.com/net/config-maps/-/merge_requests/1"
    assert sent["number"] == 1
    assert sent["target_branch"] == "main"
    assert sent["path"] == "got/banner.py"
    branch = sent["source_branch"]
    assert branch.startswith("acex/banner-")

    assert gitlab.branches[branch]["got/banner.py"] == NTP
    assert "got/banner.py" not in gitlab.branches["main"]
    (commit,) = gitlab.commits
    assert commit["start_branch"] == "main"
    assert commit["commit_message"] == "Add the banner of got"
    assert commit["actions"] == [{"action": "create", "file_path": "got/banner.py", "content": NTP}]
    (merge_request,) = gitlab.merge_requests
    assert merge_request == {
        "source_branch": branch,
        "target_branch": "main",
        "title": "Add the banner of got",
        "description": "NTP as it runs on the core switch.\n\nSent from ACEX by anna.",
        "remove_source_branch": True,
    }


def test_a_merge_request_goes_into_the_branch_the_repository_follows_not_the_default_one(env, gitlab, monkeypatch):
    gitlab.branches["stage"] = {"README.md": "# stage\n"}
    repo = repository(env, branch="stage")

    # main has this file and stage does not: it is new to the branch that is followed.
    response = send(_client(env, monkeypatch), repo, path="got/ntp.py")

    assert response.status_code == 201
    sent = response.json()
    assert sent["target_branch"] == "stage"
    assert gitlab.commits[0]["start_branch"] == "stage"
    assert gitlab.commits[0]["actions"][0]["action"] == "create"
    assert gitlab.merge_requests[0]["target_branch"] == "stage"
    assert set(gitlab.branches[sent["source_branch"]]) == {"README.md", "got/ntp.py"}


def test_every_merge_request_gets_a_branch_of_its_own_named_after_the_file(env, gitlab, monkeypatch):
    repo = repository(env)
    client = _client(env, monkeypatch)

    first = send(client, repo, path="got/Banner Ä.py").json()["source_branch"]
    second = send(client, repo, path="sto/Banner Ä.py").json()["source_branch"]

    assert first.startswith("acex/banner-")
    assert second.startswith("acex/banner-")
    assert first != second
    assert len(gitlab.merge_requests) == 2


def test_the_commit_is_written_in_the_senders_name_when_the_token_carries_an_address(env, gitlab, monkeypatch):
    repo = repository(env)
    client = _client(env, monkeypatch)
    claims = {"sub": "u-17", "preferred_username": "anna", "name": "Anna Berg", "email": "anna@example.com"}
    monkeypatch.setattr(auth, "_decode", lambda token, force_jwks_refresh=False: claims)

    assert send(client, repo).status_code == 201

    assert gitlab.commits[0]["author_name"] == "Anna Berg"
    assert gitlab.commits[0]["author_email"] == "anna@example.com"
    assert gitlab.merge_requests[0]["description"] == "Sent from ACEX by anna."


def test_the_commit_is_the_tokens_own_when_the_sender_has_no_address(env, gitlab, monkeypatch):
    repo = repository(env)

    assert send(_client(env, monkeypatch), repo).status_code == 201

    assert "author_name" not in gitlab.commits[0]
    assert "author_email" not in gitlab.commits[0]


def test_a_file_that_is_already_there_is_refused_and_nothing_is_written(env, gitlab, monkeypatch):
    repo = repository(env)

    response = send(_client(env, monkeypatch), repo, path="got/ntp.py")

    assert response.status_code == 409
    assert response.json()["detail"] == "got/ntp.py is already on main: send replace to change it"
    assert list(gitlab.branches) == ["main"]
    assert gitlab.commits == []
    assert gitlab.merge_requests == []


def test_a_file_that_is_already_there_is_changed_when_it_is_to_be_replaced(env, gitlab, monkeypatch):
    repo = repository(env)
    changed = NTP + "\n# changed\n"

    response = send(_client(env, monkeypatch), repo, path="got/ntp.py", content=changed, replace=True)

    assert response.status_code == 201
    assert gitlab.commits[0]["actions"] == [{"action": "update", "file_path": "got/ntp.py", "content": changed}]
    assert gitlab.branches["main"]["got/ntp.py"] == NTP


def test_replace_adds_the_file_when_the_path_is_free(env, gitlab, monkeypatch):
    repo = repository(env)

    response = send(_client(env, monkeypatch), repo, replace=True)

    assert response.status_code == 201
    assert gitlab.commits[0]["actions"][0]["action"] == "create"


def test_the_file_is_looked_for_on_the_followed_branch_by_its_whole_path(env, gitlab, monkeypatch):
    repo = repository(env)

    send(_client(env, monkeypatch), repo, path="got lab/ntp server.py")

    (looked,) = gitlab.sent("HEAD", "repository/files/")
    assert (
        looked.url.raw_path
        == b"/api/v4/projects/net%2Fconfig-maps/repository/files/got%20lab%2Fntp%20server.py?ref=main"
    )


@pytest.mark.parametrize(
    ("content", "why"),
    [
        ("class Ntp(ConfigMap:\n    pass\n", "line 1"),
        ("x = 1\n  y = 2\n", "line 2"),
    ],
)
def test_a_file_that_is_not_python_is_refused_before_the_git_host_is_asked(env, gitlab, monkeypatch, content, why):
    repo = repository(env)

    response = send(_client(env, monkeypatch), repo, content=content)

    assert response.status_code == 422
    assert response.json()["detail"].startswith(f"The file is not Python that can be read: {why}")
    assert gitlab.requests == []


@pytest.mark.parametrize(
    "path", ["/etc/passwd.py", "../outside.py", "a/../../b.py", ".git/hooks/x.py", "got/notes.txt", "got/", ""]
)
def test_the_path_is_a_python_file_inside_the_repository(env, gitlab, monkeypatch, path):
    repo = repository(env)

    response = send(_client(env, monkeypatch), repo, path=path)

    assert response.status_code == 422
    assert gitlab.requests == []


@pytest.mark.parametrize("field", ["content", "title"])
def test_a_merge_request_needs_a_file_and_a_title(env, gitlab, monkeypatch, field):
    repo = repository(env)

    assert send(_client(env, monkeypatch), repo, **{field: ""}).status_code == 422
    assert gitlab.requests == []


def test_a_repository_without_a_merge_request_token_sends_nothing(env, gitlab, monkeypatch):
    manager, credentials = env
    plain = manager.create(
        GitRepositoryCreate(name="plain", url=URL, auth_method="https_anonymous"), created_by="admin"
    )
    client = _client(env, monkeypatch)

    response = send(client, plain)

    assert response.status_code == 409
    assert response.json()["detail"] == "Git repository plain has no merge request token"
    assert client.get(f"/api/v1/git_repositories/{plain.id}/tree", headers=ANNA).status_code == 409
    assert gitlab.requests == []


def test_a_merge_request_token_that_has_been_deleted_sends_nothing(env, gitlab, monkeypatch):
    manager, credentials = env
    repo = repository(env)
    credentials.delete(repo.merge_request_credential_id)

    response = send(_client(env, monkeypatch), repo)

    assert response.status_code == 409
    assert f"Credential {repo.merge_request_credential_id}" in response.json()["detail"]
    assert gitlab.requests == []


def test_an_unknown_repository_is_not_found(env, gitlab, monkeypatch):
    client = _client(env, monkeypatch)

    assert client.post("/api/v1/git_repositories/999/merge_requests", json={}, headers=ANNA).status_code == 422
    body = {"path": "a.py", "content": NTP, "title": "Add a"}
    assert client.post("/api/v1/git_repositories/999/merge_requests", json=body, headers=ANNA).status_code == 404
    assert client.get("/api/v1/git_repositories/999/tree", headers=ANNA).status_code == 404


def test_merge_requests_are_for_signed_in_users(env, gitlab, monkeypatch):
    repo = repository(env)
    client = _client(env, monkeypatch)
    body = {"path": "a.py", "content": NTP, "title": "Add a"}

    assert client.post(f"/api/v1/git_repositories/{repo.id}/merge_requests", json=body).status_code == 401
    assert client.get(f"/api/v1/git_repositories/{repo.id}/tree").status_code == 401
    assert gitlab.requests == []


def test_the_merge_request_token_is_the_token_of_a_token_credential(env):
    manager, credentials = env
    login = credentials.create(
        CredentialCreate(name="login", credential_type="userpass", fields={"username": "u", "password": "p"})
    )
    plain = GitRepositoryCreate(name="maps", url=URL, auth_method="https_anonymous")

    with pytest.raises(ValueError, match="merge request token is the token of a token credential"):
        manager.create(plain.model_copy(update={"merge_request_credential_id": login.id}), created_by="admin")
    with pytest.raises(ValueError, match="Credential 999"):
        manager.create(plain.model_copy(update={"merge_request_credential_id": 999}), created_by="admin")

    repo = manager.create(plain, created_by="admin")
    with pytest.raises(ValueError, match="merge request token is the token of a token credential"):
        manager.update(repo.id, GitRepositoryUpdate(merge_request_credential_id=login.id), updated_by="admin")


def test_the_merge_request_token_is_set_and_taken_away_by_an_update(env, gitlab, monkeypatch):
    manager, credentials = env
    repo = repository(env)
    client = _client(env, monkeypatch)

    kept = manager.update(repo.id, GitRepositoryUpdate(site="got"), updated_by="admin")
    assert kept.merge_request_credential_id == repo.merge_request_credential_id

    cleared = manager.update(repo.id, GitRepositoryUpdate(merge_request_credential_id=None), updated_by="admin")
    assert cleared.merge_request_credential_id is None
    assert send(client, repo).status_code == 409

    manager.update(
        repo.id, GitRepositoryUpdate(merge_request_credential_id=repo.merge_request_credential_id), updated_by="admin"
    )
    assert send(client, repo).status_code == 201


def test_the_token_goes_to_the_repositorys_host_in_a_header_and_is_never_returned(env, gitlab, monkeypatch, caplog):
    repo = repository(env)
    client = _client(env, monkeypatch)

    with caplog.at_level(logging.DEBUG):
        sent = send(client, repo)
        tree = client.get(f"/api/v1/git_repositories/{repo.id}/tree", headers=ANNA)
        shown = client.get(f"/api/v1/git_repositories/{repo.id}", headers=ANNA)

    assert gitlab.requests
    for request in gitlab.requests:
        assert request.url.host == "gitlab.example.com"
        assert request.url.scheme == "https"
        assert request.headers["private-token"] == TOKEN
        assert TOKEN not in str(request.url)
        assert TOKEN not in request.content.decode()
    assert shown.json()["merge_request_credential_id"] == repo.merge_request_credential_id
    for answer in (sent, tree, shown):
        assert TOKEN not in answer.text
    assert TOKEN not in caplog.text
    assert "merge request 1 sent by anna for got/banner.py" in caplog.text


@pytest.mark.parametrize(
    ("instead", "said"),
    [
        (
            httpx.Response(403, json={"message": "403 Forbidden"}),
            "GitLab at gitlab.example.com did not let the token commit the file to a new branch: "
            "it needs the scope api and at least the role Developer in net/config-maps",
        ),
        (
            httpx.Response(400, json={"message": "Branch name is invalid"}),
            "GitLab at gitlab.example.com would not commit the file to a new branch (400): Branch name is invalid",
        ),
        (
            httpx.Response(400, json={"message": {"base": ["Commit message is too long", "Try again"]}}),
            "GitLab at gitlab.example.com would not commit the file to a new branch (400): "
            "base: Commit message is too long, Try again",
        ),
        (
            httpx.Response(500, text="<html>Whoops</html>"),
            "GitLab at gitlab.example.com would not commit the file to a new branch (500)",
        ),
    ],
)
def test_what_gitlab_refuses_is_passed_on_in_its_own_words(env, gitlab, monkeypatch, instead, said):
    repo = repository(env)
    gitlab.instead["commits"] = instead

    response = send(_client(env, monkeypatch), repo)

    assert response.status_code == 502
    assert response.json()["detail"] == said
    assert gitlab.merge_requests == []


def test_a_wrong_token_is_said_to_be_wrong(env, gitlab, monkeypatch):
    repo = repository(env, token="s3cret-revoked-token")
    client = _client(env, monkeypatch)
    wrong = "GitLab at gitlab.example.com refused the token: it is wrong, revoked or has expired"

    sent = send(client, repo)
    tree = client.get(f"/api/v1/git_repositories/{repo.id}/tree", headers=ANNA)

    assert (sent.status_code, sent.json()["detail"]) == (502, wrong)
    assert (tree.status_code, tree.json()["detail"]) == (502, wrong)
    assert "s3cret-revoked-token" not in sent.text + tree.text


def test_a_project_that_gitlab_does_not_show_the_token_is_named(env, gitlab, monkeypatch):
    repo = repository(env, url="https://gitlab.example.com/net/other.git")
    client = _client(env, monkeypatch)
    missing = (
        "gitlab.example.com has no GitLab project net/other that the token can see (404). "
        "Merge requests are sent to GitLab only"
    )

    sent = send(client, repo)
    tree = client.get(f"/api/v1/git_repositories/{repo.id}/tree", headers=ANNA)

    assert (sent.status_code, sent.json()["detail"]) == (502, missing)
    assert (tree.status_code, tree.json()["detail"]) == (502, missing)


def test_a_host_that_is_not_gitlab_is_said_not_to_answer_as_gitlab(env, gitlab, monkeypatch):
    repo = repository(env)
    gitlab.instead["tree"] = httpx.Response(200, text="<html>Sign in</html>")
    gitlab.instead["merge_requests"] = httpx.Response(200, json=[])
    client = _client(env, monkeypatch)
    not_gitlab = "gitlab.example.com did not answer as GitLab does: merge requests are sent to GitLab only"

    tree = client.get(f"/api/v1/git_repositories/{repo.id}/tree", headers=ANNA)
    sent = send(client, repo)

    assert (tree.status_code, tree.json()["detail"]) == (502, not_gitlab)
    assert (sent.status_code, sent.json()["detail"]) == (502, not_gitlab)


def test_a_merge_request_that_cannot_be_opened_leaves_no_branch_behind(env, gitlab, monkeypatch):
    repo = repository(env)
    gitlab.instead["merge_requests"] = httpx.Response(409, json={"message": ["Another open merge request exists"]})

    response = send(_client(env, monkeypatch), repo)

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "GitLab at gitlab.example.com would not open the merge request (409): Another open merge request exists"
    )
    assert len(gitlab.commits) == 1
    assert list(gitlab.branches) == ["main"]
    (removed,) = gitlab.sent("DELETE", "repository/branches/")
    assert removed.url.raw_path.startswith(b"/api/v4/projects/net%2Fconfig-maps/repository/branches/acex%2Fbanner-")


def test_a_host_that_cannot_be_reached_says_so(env, monkeypatch):
    manager, credentials = env

    def unreachable(request):
        raise httpx.ConnectError("[Errno 61] Connection refused")

    manager._http_transport = httpx.MockTransport(unreachable)
    repo = repository(env)
    client = _client(env, monkeypatch)
    said = "Could not reach GitLab at gitlab.example.com: [Errno 61] Connection refused"

    sent = send(client, repo)
    tree = client.get(f"/api/v1/git_repositories/{repo.id}/tree", headers=ANNA)

    assert (sent.status_code, sent.json()["detail"]) == (502, said)
    assert (tree.status_code, tree.json()["detail"]) == (502, said)


def test_the_tree_lists_every_directory_and_file_of_the_followed_branch(env, gitlab, monkeypatch):
    gitlab.page_size = 2
    gitlab.branches["main"]["got/access/vlan.py"] = NTP
    gitlab.branches["other"] = {"elsewhere.py": NTP}
    repo = repository(env)

    response = _client(env, monkeypatch).get(f"/api/v1/git_repositories/{repo.id}/tree", headers=ANNA)

    assert response.status_code == 200
    assert response.json() == {
        "branch": "main",
        "directories": ["got", "got/access", "sto"],
        "files": ["README.md", "got/access/vlan.py", "got/ntp.py", "sto/vlan.py"],
        "truncated": False,
    }
    pages = gitlab.sent("GET", "repository/tree")
    assert len(pages) == 4
    assert pages[0].url.params["ref"] == "main"
    assert pages[0].url.params["recursive"] == "true"


def test_a_tree_that_is_too_large_is_cut_short_and_says_so(env, gitlab, monkeypatch):
    gitlab.page_size = 1
    monkeypatch.setattr(gitlab_api, "_MAX_PAGES", 3)
    repo = repository(env)

    tree = _client(env, monkeypatch).get(f"/api/v1/git_repositories/{repo.id}/tree", headers=ANNA).json()

    assert tree["truncated"] is True
    assert len(tree["directories"]) + len(tree["files"]) == 3
    assert len(gitlab.sent("GET", "repository/tree")) == 3


def test_the_next_page_is_never_asked_of_another_host(env, gitlab, monkeypatch):
    elsewhere = '<https://gitlab.example.com.evil.example.net/api/v4/projects/1/repository/tree?page=2>; rel="next"'
    gitlab.instead["tree"] = httpx.Response(200, json=[{"path": "got", "type": "tree"}], headers={"link": elsewhere})
    repo = repository(env)

    tree = _client(env, monkeypatch).get(f"/api/v1/git_repositories/{repo.id}/tree", headers=ANNA).json()

    assert tree == {"branch": "main", "directories": ["got"], "files": [], "truncated": True}
    assert [request.url.host for request in gitlab.requests] == ["gitlab.example.com"]


def test_a_branch_that_the_git_host_does_not_have_is_named(env, gitlab, monkeypatch):
    repo = repository(env, branch="gone")
    client = _client(env, monkeypatch)

    tree = client.get(f"/api/v1/git_repositories/{repo.id}/tree", headers=ANNA)
    sent = send(client, repo)

    assert (tree.status_code, tree.json()["detail"]) == (
        502,
        "GitLab at gitlab.example.com has no branch gone in net/config-maps",
    )
    assert sent.status_code == 502
    assert "You can only create or edit files when you are on a branch" in sent.json()["detail"]


@pytest.mark.parametrize(
    ("url", "host", "project"),
    [
        ("https://gitlab.example.com/net/config-maps.git", "gitlab.example.com", b"net%2Fconfig-maps"),
        ("https://gitlab.example.com/net/config-maps", "gitlab.example.com", b"net%2Fconfig-maps"),
        ("https://gitlab.example.com/net/config-maps/", "gitlab.example.com", b"net%2Fconfig-maps"),
        (
            "https://gitlab.example.com:8443/customers/acme/site-1.git",
            "gitlab.example.com",
            b"customers%2Facme%2Fsite-1",
        ),
    ],
)
def test_the_project_is_the_one_the_repositorys_url_names(url, host, project):
    asked = []

    def answer(request):
        asked.append(request)
        return httpx.Response(200, json=[])

    with gitlab_api.GitLab(url, TOKEN, transport=httpx.MockTransport(answer)) as api:
        assert api.tree("main") == ([], [], False)

    assert asked[0].url.host == host
    assert asked[0].url.port == (8443 if ":8443" in url else None)
    assert asked[0].url.raw_path.startswith(b"/api/v4/projects/" + project + b"/repository/tree?")


def test_a_url_without_a_project_is_refused():
    with pytest.raises(GitHostError, match="names no project"):
        gitlab_api.GitLab("https://gitlab.example.com/", TOKEN)


def test_a_gitlab_signed_by_an_internal_ca_is_trusted_with_the_repositorys_ca_certificate(tmp_path):
    db = _Db()
    credentials = CredentialManager(db, Fernet.generate_key().decode())
    settings = GitSyncSettings(checkout_dir=str(tmp_path / "checkouts"))
    manager = GitSyncManager(db, ConfigCompiler(db), credentials, settings, git=Git(allowed_protocols=("file",)))
    listing = tmp_path / "www" / "api" / "v4" / "projects" / "net" / "maps" / "repository" / "tree"
    listing.parent.mkdir(parents=True)
    listing.write_text(json.dumps([{"path": "got", "type": "tree"}, {"path": "got/ntp.py", "type": "blob"}]))
    ca_pem, server = _internal_ca_host(tmp_path)
    try:
        repo = repository((manager, credentials), url=f"https://127.0.0.1:{server.server_port}/net/maps.git")

        with pytest.raises(GitHostError, match="Could not reach GitLab at 127.0.0.1.*certificate"):
            manager.tree(repo.id)

        manager.update(repo.id, GitRepositoryUpdate(ca_certificate=ca_pem), updated_by="admin")
        tree = manager.tree(repo.id)
        assert (tree.directories, tree.files) == (["got"], ["got/ntp.py"])
    finally:
        server.shutdown()


def test_the_manager_refuses_as_the_api_does(env, gitlab):
    manager, credentials = env
    repo = repository(env)
    there = MergeRequestCreate(path="got/ntp.py", content=NTP, title="Add NTP")

    with pytest.raises(GitRepositoryConflict, match="already on main"):
        manager.merge_request(repo.id, there, sent_by="anna")
    with pytest.raises(ValueError, match="not Python that can be read"):
        manager.merge_request(repo.id, there.model_copy(update={"content": "def broken(:\n"}), sent_by="anna")
