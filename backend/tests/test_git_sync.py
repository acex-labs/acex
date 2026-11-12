"""ConfigMaps read from a git repository: loaded when it is added, loaded again only when its branch moves or
its settings change, and never replaced by a commit in which a file fails to import. Repositories are local
here (file://); the token goes to git through the environment only."""

import subprocess
import sys
from pathlib import Path

import pytest
from acex.api import auth
from acex.api.routers import git_repositories
from acex.compilers.config_compiler import ConfigCompiler
from acex.credentials.credential_manager import CredentialManager
from acex.git_sync import Git, GitAuth, GitError, GitSyncManager, HttpsTokenAuth
from acex.settings import GitSyncSettings
from acex_devkit.models.credential import CredentialCreate
from acex_devkit.models.git_repository import GitAuthMethod, GitRepositoryCreate, GitRepositoryUpdate
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

MAP = """from acex.config_map import ConfigMap


class {cls}(ConfigMap):
    def compile(self, context):
        pass


{var} = {cls}()
"""


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _CountingGit(Git):
    def __init__(self):
        super().__init__(timeout=30, allowed_protocols=("file",))
        self.checkouts = 0

    def checkout(self, *args, **kwargs):
        self.checkouts += 1
        return super().checkout(*args, **kwargs)


class _Remote:
    """A repository to sync from, committed to as the test goes."""

    def __init__(self, path: Path):
        self.path = path
        self.git("init", "--quiet", "--initial-branch=main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")

    @property
    def url(self) -> str:
        return self.path.as_uri()

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.path, check=True, capture_output=True, text=True).stdout

    def commit(self, files: dict[str, str | None]) -> str:
        for name, content in files.items():
            target = self.path / name
            if content is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "change")
        return self.git("rev-parse", "HEAD").strip()


@pytest.fixture(autouse=True)
def _forget_modules():
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        if name.startswith("gitsync_"):
            del sys.modules[name]


@pytest.fixture
def remote(tmp_path):
    (tmp_path / "remote").mkdir()
    return _Remote(tmp_path / "remote")


@pytest.fixture
def env(tmp_path):
    db = _Db()
    credentials = CredentialManager(db, Fernet.generate_key().decode())
    compiler = ConfigCompiler(db)
    git = _CountingGit()
    settings = GitSyncSettings(checkout_dir=str(tmp_path / "checkouts"))
    manager = GitSyncManager(db, compiler, credentials, settings, git=git)
    return manager, compiler, credentials, git


def anonymous(remote, **fields) -> GitRepositoryCreate:
    # Validation wants https; the tests sync from a local path, so the URL is set past it.
    payload = GitRepositoryCreate(
        name="maps", url="https://example.com/maps.git", auth_method=GitAuthMethod.HTTPS_ANONYMOUS, **fields
    )
    return payload.model_copy(update={"url": remote.url})


def names(compiler) -> list[str]:
    return sorted(m.name for m in compiler.config_maps)


def test_an_added_repository_has_its_config_maps_loaded(env, remote):
    manager, compiler, _, _ = env
    commit = remote.commit({"gitsync_a.py": MAP.format(cls="Alpha", var="alpha")})

    repo = manager.create(anonymous(remote), created_by="admin")

    assert repo.commit == commit
    assert repo.last_error is None
    assert repo.config_maps == ["gitsync_a.py:alpha"]
    assert names(compiler) == ["Alpha"]
    assert str(Path(manager.checkout_root)) in compiler.source_roots[0]


def test_only_a_moved_branch_is_fetched_again(env, remote):
    manager, compiler, _, git = env
    remote.commit({"gitsync_a.py": MAP.format(cls="Alpha", var="alpha")})
    manager.create(anonymous(remote), created_by="admin")

    manager.sync_all()
    assert git.checkouts == 1

    commit = remote.commit({"gitsync_a.py": None, "gitsync_b.py": MAP.format(cls="Beta", var="beta")})
    manager.sync_all()

    assert git.checkouts == 2
    assert names(compiler) == ["Beta"]
    assert manager.repositories()[0].commit == commit


def test_a_commit_that_fails_to_import_keeps_the_config_maps_in_use(env, remote):
    manager, compiler, _, git = env
    good = remote.commit({"gitsync_a.py": MAP.format(cls="Alpha", var="alpha")})
    repo = manager.create(anonymous(remote), created_by="admin")

    remote.commit({"gitsync_a.py": MAP.format(cls="Alpha", var="alpha") + "\ndef broken(:\n"})
    manager.sync_all()

    repo = manager.repository(repo.id)
    assert names(compiler) == ["Alpha"]
    assert repo.commit == good
    assert "gitsync_a.py: SyntaxError" in repo.last_error

    # The broken commit is not fetched again at every poll; a forced sync retries it.
    manager.sync_all()
    assert git.checkouts == 2
    manager.sync(repo.id, force=True)
    assert git.checkouts == 3


def test_config_maps_are_read_from_the_repositorys_path(env, remote):
    manager, compiler, _, _ = env
    remote.commit(
        {
            "gitsync_root.py": MAP.format(cls="Root", var="root"),
            "config_maps/gitsync_sub.py": MAP.format(cls="Sub", var="sub"),
        }
    )

    repo = manager.create(anonymous(remote, path="config_maps"), created_by="admin")
    assert names(compiler) == ["Sub"]

    repo = manager.update(repo.id, GitRepositoryUpdate(path="missing"), updated_by="admin")
    assert "missing: no such directory" in repo.last_error
    assert names(compiler) == ["Sub"]


def test_a_disabled_or_deleted_repository_has_its_config_maps_dropped(env, remote):
    manager, compiler, _, _ = env
    remote.commit({"gitsync_a.py": MAP.format(cls="Alpha", var="alpha")})
    repo = manager.create(anonymous(remote), created_by="admin")

    manager.update(repo.id, GitRepositoryUpdate(enabled=False), updated_by="admin")
    assert compiler.config_maps == []

    manager.update(repo.id, GitRepositoryUpdate(enabled=True), updated_by="admin")
    assert names(compiler) == ["Alpha"]

    manager.delete(repo.id)
    assert compiler.config_maps == []
    assert not (manager.checkout_root / str(repo.id)).exists()


def test_an_unreachable_repository_keeps_its_config_maps_and_says_why(env, remote):
    manager, compiler, _, _ = env
    remote.commit({"gitsync_a.py": MAP.format(cls="Alpha", var="alpha")})
    repo = manager.create(anonymous(remote), created_by="admin")

    remote.path.rename(remote.path.with_name("gone"))
    manager.sync_all()

    assert names(compiler) == ["Alpha"]
    assert "Could not reach the repository" in manager.repository(repo.id).last_error


def test_a_restarted_process_loads_the_last_checkout_when_the_repository_is_unreachable(env, remote, tmp_path):
    manager, _, credentials, _ = env
    remote.commit({"gitsync_a.py": MAP.format(cls="Alpha", var="alpha")})
    manager.create(anonymous(remote), created_by="admin")
    remote.path.rename(remote.path.with_name("gone"))

    restarted = ConfigCompiler(manager.db)
    GitSyncManager(manager.db, restarted, credentials, manager.settings, git=_CountingGit()).sync_all()

    assert names(restarted) == ["Alpha"]


def test_a_token_repository_needs_a_token_credential(env, remote):
    manager, _, credentials, _ = env
    login = credentials.create(
        CredentialCreate(name="login", credential_type="userpass", fields={"username": "u", "password": "p"})
    )

    with pytest.raises(ValueError, match="needs a token credential"):
        manager.create(
            GitRepositoryCreate(name="maps", url="https://example.com/m.git", credential_id=login.id),
            created_by="admin",
        )
    with pytest.raises(ValueError, match="Credential 999"):
        manager.create(
            GitRepositoryCreate(name="maps", url="https://example.com/m.git", credential_id=999), created_by="admin"
        )


def test_the_token_reaches_git_through_the_environment_only():
    auth = HttpsTokenAuth(token="s3cret-token", username="bot")
    assert all("s3cret-token" not in option for option in auth.config())

    git = Git(allowed_protocols=("https",))
    filled = subprocess.run(
        ["git", *auth.config(), "credential", "fill"],
        input="protocol=https\nhost=example.com\n\n",
        env={**auth.env(), "GIT_CONFIG_NOSYSTEM": "1", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "username=bot" in filled
    assert "password=s3cret-token" in filled

    # git's own messages may echo what it was given; the token is taken out of them.
    with pytest.raises(GitError) as failed:
        git._run(["ls-remote", "--", "https://s3cret-token@127.0.0.1:1/x.git"], auth)
    assert "s3cret-token" not in str(failed.value)


def test_only_allowed_protocols_are_used(remote):
    remote.commit({"gitsync_a.py": MAP.format(cls="Alpha", var="alpha")})
    with pytest.raises(GitError):
        Git(allowed_protocols=("https",)).remote_commit(remote.url, "main", GitAuth())


# ── API ──────────────────────────────────────────────────────────


def _client(env, monkeypatch):
    manager, *_ = env
    monkeypatch.setattr(auth, "OIDC_ISSUER_URL", "https://idp.example.com")
    # The bearer token here is the caller's username.
    monkeypatch.setattr(auth, "_decode", lambda token, force_jwks_refresh=False: {"sub": token})
    engine = type("Engine", (), {"git_sync": manager, "settings": type("S", (), {"git_sync": manager.settings})})
    app = FastAPI()
    app.include_router(git_repositories.create_router(engine))
    return TestClient(app)


def test_the_api_is_open_to_every_signed_in_user_and_no_one_else(env, monkeypatch):
    client = _client(env, monkeypatch)

    assert client.get("/api/v1/git_repositories").status_code == 401
    assert client.get("/api/v1/git_repositories", headers={"Authorization": "Bearer anna"}).json() == []


def test_the_api_adds_syncs_and_deletes_a_repository(env, monkeypatch, remote):
    manager, compiler, credentials, _ = env
    client = _client(env, monkeypatch)
    admin = {"Authorization": "Bearer anna"}
    token = credentials.create(CredentialCreate(name="pat", credential_type="token", fields={"token": "t"}))

    rejected = client.post(
        "/api/v1/git_repositories", json={"name": "m", "url": "http://example.com/m.git"}, headers=admin
    )
    assert rejected.status_code == 422

    created = client.post(
        "/api/v1/git_repositories",
        json={"name": "maps", "url": "https://127.0.0.1:1/maps.git", "credential_id": token.id},
        headers=admin,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["created_by"] == "anna"
    assert body["last_error"].startswith("Could not reach the repository")

    duplicate = client.post(
        "/api/v1/git_repositories",
        json={"name": "maps", "url": "https://127.0.0.1:1/maps.git", "credential_id": token.id},
        headers=admin,
    )
    assert duplicate.status_code == 409

    assert client.post(f"/api/v1/git_repositories/{body['id']}/sync", headers=admin).status_code == 200
    assert client.delete(f"/api/v1/git_repositories/{body['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/v1/git_repositories/{body['id']}", headers=admin).status_code == 404


# ── A host signed by an internal CA ──────────────────────────────


def _internal_ca_host(tmp_path):
    """An HTTPS server for 127.0.0.1 whose certificate an internal CA signed. Returns (ca_pem, server)."""
    import datetime
    import ipaddress
    import ssl
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    now = datetime.datetime.now(datetime.UTC)

    def cert(subject, issuer, key, signer, ca, san=None):
        builder = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer)]))
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        )
        if san:
            builder = builder.add_extension(x509.SubjectAlternativeName(san), critical=False)
        return builder.sign(signer, hashes.SHA256())

    ca_key, host_key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    ca = cert("Internal CA", "Internal CA", ca_key, ca_key, ca=True)
    host = cert(
        "127.0.0.1", "Internal CA", host_key, ca_key, ca=False, san=[x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    )
    (tmp_path / "host.pem").write_bytes(
        host.public_bytes(serialization.Encoding.PEM)
        + host_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "host.pem")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path / "www")))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return ca.public_bytes(serialization.Encoding.PEM).decode(), server


def test_a_host_signed_by_an_internal_ca_is_trusted_with_its_ca_certificate(env, tmp_path):
    manager, _, _, _ = env
    manager._git = Git(timeout=30)  # https only, as in production
    # Served over git's plain HTTP protocol, which is enough to ask a branch for its commit.
    (tmp_path / "www" / "maps.git").mkdir(parents=True)
    remote = _Remote(tmp_path / "www" / "maps.git")
    commit = remote.commit({"gitsync_a.py": MAP.format(cls="Alpha", var="alpha")})
    remote.git("update-server-info")
    ca_pem, server = _internal_ca_host(tmp_path)
    url = f"https://127.0.0.1:{server.server_port}/maps.git/.git"
    try:
        repo = manager.create(
            GitRepositoryCreate(name="maps", url=url, auth_method=GitAuthMethod.HTTPS_ANONYMOUS), created_by="admin"
        )
        # OpenSSL words it "SSL certificate problem", GnuTLS "server certificate verification failed".
        assert "certificate" in repo.last_error.lower()

        trusted = manager.update(repo.id, GitRepositoryUpdate(ca_certificate=ca_pem), updated_by="admin")
        assert "certificate" not in (trusted.last_error or "").lower()
        ca_file = manager.checkout_root / f"{repo.id}.ca.pem"
        assert manager.git.remote_commit(url, "main", GitAuth(), ca_file) == commit
    finally:
        server.shutdown()


def test_a_ca_certificate_must_be_pem(env, remote):
    manager, _, _, _ = env
    with pytest.raises(ValueError, match="PEM"):
        anonymous(remote, ca_certificate="not a certificate")
    bad = "-----BEGIN CERTIFICATE-----\nnope\n-----END CERTIFICATE-----"
    with pytest.raises(ValueError, match="not valid PEM"):
        manager.create(anonymous(remote, ca_certificate=bad), created_by="admin")
