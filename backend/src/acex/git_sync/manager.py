"""Git repositories that ConfigMaps are read from, and keeping each API process's ConfigMaps in step with them.

Each API process holds its ConfigMaps in memory, so each one checks the repositories itself: at startup,
every `poll_interval_seconds` after that, and at once in the process that answers a change or a sync
request. Asking costs one `git ls-remote`; only a branch that moved, or a repository whose settings
changed, is fetched and loaded again.

A new commit replaces the repository's ConfigMaps only when every file in it imports. If one fails, the
ConfigMaps already loaded stay in use and `last_error` says which file failed, so a broken push never
leaves devices compiled from half of the ConfigMaps.
"""

import asyncio
import contextlib
import fcntl
import logging
import shutil
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

from acex.compilers.config_compiler import ConfigCompiler, ConfigMapLoadError
from acex.git_sync.git import Git, GitAuth, GitError, HttpsTokenAuth
from acex.models.git_repository import GitRepositoryRow
from acex.settings import GitSyncSettings
from acex_devkit.models.git_repository import (
    GIT_AUTH_CREDENTIAL_TYPES,
    GitAuthMethod,
    GitRepositoryCreate,
    GitRepositoryResponse,
    GitRepositoryUpdate,
)
from cryptography import x509
from fastapi import HTTPException
from sqlmodel import select

logger = logging.getLogger("acex.git_sync")

#: The fields that decide what is checked out and loaded; changing one loads the repository again.
_SOURCE_FIELDS = ("url", "branch", "path", "auth_method", "credential_id", "username")


class GitRepositoryNotFound(LookupError):
    pass


class GitRepositoryConflict(ValueError):
    pass


class GitSyncManager:
    def __init__(
        self,
        db_manager,
        compiler: ConfigCompiler,
        credential_manager,
        settings: GitSyncSettings,
        git: Git | None = None,
    ):
        self.db = db_manager
        self.compiler = compiler
        self.credentials = credential_manager
        self.settings = settings
        self.checkout_root = Path(settings.checkout_dir or Path(tempfile.gettempdir()) / "acex-git-sync")
        self._git = git
        # One sync at a time in this process: the poll and a request must not check out the same directory.
        self._lock = threading.RLock()
        # Repository id -> (its source fields, the commit fetched for them) in this process. A commit whose
        # ConfigMaps failed to load is kept too, so it is not fetched again at every poll.
        self._fetched: dict[int, tuple[tuple, str]] = {}

    @property
    def git(self) -> Git:
        # Made when first needed, so a backend without git still starts and serves everything else.
        if self._git is None:
            self._git = Git(timeout=self.settings.timeout_seconds)
        return self._git

    # ── Repositories ─────────────────────────────────────────────

    def repositories(self) -> list[GitRepositoryResponse]:
        with self._session() as session:
            rows = session.exec(select(GitRepositoryRow).order_by(GitRepositoryRow.name)).all()
            return [self.response(row) for row in rows]

    def repository(self, repo_id: int) -> GitRepositoryResponse:
        with self._session() as session:
            return self.response(self._row(session, repo_id))

    def create(self, payload: GitRepositoryCreate, *, created_by: str) -> GitRepositoryResponse:
        """Save the repository and, when it is enabled, sync it at once so the answer says how that went."""
        self._check_credential(payload.auth_method, payload.credential_id)
        self._check_ca_certificate(payload.ca_certificate)
        with self._session() as session:
            self._check_name_free(session, payload.name)
            row = GitRepositoryRow(**payload.model_dump(mode="json"), created_by=created_by, updated_by=created_by)
            session.add(row)
            session.commit()
            session.refresh(row)
            repo_id = row.id
        if payload.enabled:
            self.sync(repo_id)
        return self.repository(repo_id)

    def update(self, repo_id: int, payload: GitRepositoryUpdate, *, updated_by: str) -> GitRepositoryResponse:
        """Change the fields sent. A change to what is checked out loads the repository again at once."""
        changes = payload.model_dump(mode="json", include=payload.model_fields_set)
        with self._session() as session:
            row = self._row(session, repo_id)
            for field, value in changes.items():
                # Only these can be cleared; the rest keep their value when sent as null.
                if value is not None or field in ("credential_id", "username", "ca_certificate"):
                    setattr(row, field, value)
            if "name" in changes:
                self._check_name_free(session, row.name, but=repo_id)
            if GIT_AUTH_CREDENTIAL_TYPES[GitAuthMethod(row.auth_method)] is None:
                row.credential_id = None
            self._check_credential(GitAuthMethod(row.auth_method), row.credential_id)
            self._check_ca_certificate(row.ca_certificate)
            row.updated_by = updated_by
            row.updated_at = datetime.now(UTC)
            session.add(row)
            session.commit()
        self.sync(repo_id)
        return self.repository(repo_id)

    def delete(self, repo_id: int) -> None:
        """Delete the repository: its ConfigMaps are no longer used and its checkout is removed."""
        with self._session() as session:
            session.delete(self._row(session, repo_id))
            session.commit()
        with self._lock:
            self._forget(repo_id)
            with self._checkout_lock(repo_id):
                shutil.rmtree(self._checkout_dir(repo_id), ignore_errors=True)
                (self.checkout_root / f"{repo_id}.ca.pem").unlink(missing_ok=True)

    # ── Syncing ──────────────────────────────────────────────────

    def sync(self, repo_id: int, force: bool = False) -> GitRepositoryResponse:
        """Load the repository's ConfigMaps again if its branch has moved or its settings changed.

        `force` fetches and loads even when nothing has, for example to retry a commit that failed.
        """
        with self._lock:
            with self._session() as session:
                row = self._row(session, repo_id)
                if row.enabled:
                    self._sync_row(session, row, force)
                else:
                    self._forget(repo_id)
        return self.repository(repo_id)

    def sync_all(self) -> None:
        """Bring every enabled repository up to date, and drop the ConfigMaps of any no longer enabled."""
        with self._lock, self._session() as session:
            rows = session.exec(select(GitRepositoryRow)).all()
            enabled = {row.id for row in rows if row.enabled}
            for repo_id in {*self._fetched, *self._loaded_ids()} - enabled:
                self._forget(repo_id)
            for row in rows:
                if row.enabled:
                    try:
                        self._sync_row(session, row, force=False)
                    except Exception:
                        logger.exception(f"Syncing git repository {row.name} failed")

    async def run(self) -> None:
        """Sync every repository now, then every `poll_interval_seconds`. Started with the API."""
        while True:
            try:
                await asyncio.to_thread(self.sync_all)
            except Exception:
                logger.exception("Syncing git repositories failed")
            await asyncio.sleep(self.settings.poll_interval_seconds)

    def _sync_row(self, session, row: GitRepositoryRow, force: bool) -> None:
        source = tuple(getattr(row, field) for field in _SOURCE_FIELDS)
        row.last_checked_at = datetime.now(UTC)
        try:
            auth = self._auth(row)
        except GitError as exc:
            self._failed(session, row, str(exc))
            return
        try:
            ca_file = self._ca_file(row)
            commit = self.git.remote_commit(row.url, row.branch, auth, ca_file)
        except (GitError, OSError) as exc:
            # Unreachable: keep what is loaded. A process that has nothing yet, just started, loads the
            # checkout that the last run left, if it is of these same settings.
            if not self.compiler.has_source(self._key(row.id)):
                self._load_last_checkout(row, source)
            self._failed(session, row, f"Could not reach the repository: {exc}")
            return

        if not force and self._fetched.get(row.id) == (source, commit):
            session.add(row)
            session.commit()
            return

        try:
            with self._checkout_lock(row.id):
                commit = self.git.checkout(row.url, row.branch, auth, self._checkout_dir(row.id), ca_file)
                self._fetched[row.id] = (source, commit)
                maps = self._load(row)
        except (GitError, ConfigMapLoadError, OSError) as exc:
            self._failed(session, row, str(exc))
            return

        self.compiler.set_source(self._key(row.id), str(self._map_dir(row)), maps)
        logger.info(f"Loaded {len(maps)} ConfigMap(s) from git repository {row.name} at {commit[:12]}")
        row.commit = commit
        row.last_synced_at = datetime.now(UTC)
        row.last_error = None
        session.add(row)
        session.commit()

    def _load(self, row: GitRepositoryRow) -> list:
        directory = self._map_dir(row)
        if not directory.is_dir():
            raise ConfigMapLoadError([f"{row.path or '.'}: no such directory on branch {row.branch}"])
        return self.compiler.load_config_maps(str(directory), strict=True)

    def _load_last_checkout(self, row: GitRepositoryRow, source: tuple) -> None:
        if row.commit is None or self.git.head(self._checkout_dir(row.id)) != row.commit:
            return
        try:
            with self._checkout_lock(row.id):
                maps = self._load(row)
        except (ConfigMapLoadError, OSError):
            return
        self.compiler.set_source(self._key(row.id), str(self._map_dir(row)), maps)
        self._fetched[row.id] = (source, row.commit)
        logger.warning(f"Git repository {row.name} unreachable; loaded its last checkout at {row.commit[:12]}")

    def _failed(self, session, row: GitRepositoryRow, error: str) -> None:
        logger.warning(f"Git repository {row.name}: {error}")
        row.last_error = error
        session.add(row)
        session.commit()

    def _forget(self, repo_id: int) -> None:
        self.compiler.remove_source(self._key(repo_id))
        self._fetched.pop(repo_id, None)

    def _loaded_ids(self) -> set[int]:
        return {int(key.removeprefix("git:")) for key in self.compiler.source_keys() if key.startswith("git:")}

    # ── Helpers ──────────────────────────────────────────────────

    def response(self, row: GitRepositoryRow) -> GitRepositoryResponse:
        repository = GitRepositoryResponse.model_validate(row)
        repository.config_maps = self.compiler.source_names(self._key(row.id))
        return repository

    def _auth(self, row: GitRepositoryRow) -> GitAuth:
        method = GitAuthMethod(row.auth_method)
        if method is GitAuthMethod.HTTPS_ANONYMOUS:
            return GitAuth()
        if row.credential_id is None:
            raise GitError(f"auth_method {method} needs a credential")
        try:
            secret = self.credentials.get_secret(row.credential_id)
        except HTTPException as exc:
            raise GitError(f"Credential {row.credential_id}: {exc.detail}") from exc
        token = secret.fields.get("token")
        if not token:
            raise GitError(f"Credential {row.credential_id} has no token")
        return HttpsTokenAuth(token=token, username=row.username or "x-access-token")

    def _ca_file(self, row: GitRepositoryRow) -> Path | None:
        """The repository's CA certificates as a file git can read, or None to trust only the system's."""
        path = self.checkout_root / f"{row.id}.ca.pem"
        if not row.ca_certificate:
            path.unlink(missing_ok=True)
            return None
        self.checkout_root.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_text() != row.ca_certificate:
            path.write_text(row.ca_certificate)
        return path

    @staticmethod
    def _check_ca_certificate(pem: str | None) -> None:
        if not pem:
            return
        try:
            x509.load_pem_x509_certificates(pem.encode())
        except ValueError as exc:
            raise ValueError(f"ca_certificate is not valid PEM: {exc}") from exc

    def _check_credential(self, method: GitAuthMethod, credential_id: int | None) -> None:
        wanted = GIT_AUTH_CREDENTIAL_TYPES[method]
        if wanted is None:
            return
        if credential_id is None:
            raise ValueError(f"auth_method {method} needs a credential_id")
        try:
            credential = self.credentials.get(credential_id)
        except HTTPException as exc:
            raise ValueError(f"Credential {credential_id}: {exc.detail}") from exc
        if credential.credential_type != wanted:
            raise ValueError(
                f"auth_method {method} needs a {wanted} credential; "
                f"credential {credential_id} is {credential.credential_type}"
            )

    def _check_name_free(self, session, name: str, but: int | None = None) -> None:
        existing = session.exec(select(GitRepositoryRow).where(GitRepositoryRow.name == name)).first()
        if existing is not None and existing.id != but:
            raise GitRepositoryConflict(f"A git repository named {name} already exists")

    def _row(self, session, repo_id: int) -> GitRepositoryRow:
        row = session.get(GitRepositoryRow, repo_id)
        if row is None:
            raise GitRepositoryNotFound(f"No git repository {repo_id}")
        return row

    @staticmethod
    def _key(repo_id: int) -> str:
        return f"git:{repo_id}"

    def _checkout_dir(self, repo_id: int) -> Path:
        return self.checkout_root / str(repo_id)

    def _map_dir(self, row: GitRepositoryRow) -> Path:
        return self._checkout_dir(row.id) / row.path if row.path else self._checkout_dir(row.id)

    @contextlib.contextmanager
    def _checkout_lock(self, repo_id: int):
        """Held while a checkout is changed or read, so API processes sharing a checkout_dir take turns."""
        self.checkout_root.mkdir(parents=True, exist_ok=True)
        with open(self.checkout_root / f"{repo_id}.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    @contextlib.contextmanager
    def _session(self):
        session = next(self.db.get_session())
        try:
            yield session
        finally:
            session.close()
