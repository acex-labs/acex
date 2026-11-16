"""The git command line, as the sync needs it: ask a branch for its commit, and check that commit out.

Secrets never go on a command line, in a URL or into `.git/config`: git reads them from the environment
of the one command that needs them, through a credential helper given with `-c`.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class GitError(RuntimeError):
    """A git command failed. The message is git's own, with any secret taken out."""


@dataclass(frozen=True)
class GitAuth:
    """How git signs in. The base signs in as nobody; a new method is a subclass (an SSH key later)."""

    def config(self) -> list[str]:
        """`-c` options for the command."""
        return []

    def env(self) -> dict[str, str]:
        """Environment for the command. Secrets go here, never in `config()`."""
        return {}

    def secrets(self) -> list[str]:
        """Values to scrub from git's output before it is shown or stored."""
        return []


# Answers git's credential request from the environment. The command line names the variables only.
_ENV_HELPER = '!f() { echo "username=${ACEX_GIT_USERNAME}"; echo "password=${ACEX_GIT_PASSWORD}"; }; f'


@dataclass(frozen=True)
class HttpsTokenAuth(GitAuth):
    token: str = field(repr=False)
    #: Most hosts take any username with a token; Bitbucket wants the account's.
    username: str = "x-access-token"

    def config(self) -> list[str]:
        # The empty helper first drops any helper the host has configured, so only ours answers.
        return ["-c", "credential.helper=", "-c", f"credential.helper={_ENV_HELPER}"]

    def env(self) -> dict[str, str]:
        return {"ACEX_GIT_USERNAME": self.username, "ACEX_GIT_PASSWORD": self.token}

    def secrets(self) -> list[str]:
        return [self.token]


class Git:
    def __init__(self, timeout: float = 120, allowed_protocols: tuple[str, ...] = ("https",)):
        """`allowed_protocols` are the transports git may use; tests add `file`."""
        if shutil.which("git") is None:
            raise GitError("git is not installed: syncing ConfigMaps from a repository needs the git command")
        self.timeout = timeout
        self.allowed_protocols = allowed_protocols

    def remote_commit(self, url: str, branch: str, auth: GitAuth, ca_file: Path | None = None) -> str:
        """The commit `branch` points at in the repository at `url`, without fetching anything.

        `ca_file` holds PEM certificates to trust for the host, besides the system's.
        """
        out = self._run(["ls-remote", "--", url, f"refs/heads/{branch}"], auth, ca_file=ca_file)
        for line in out.splitlines():
            sha, _, ref = line.partition("\t")
            if ref == f"refs/heads/{branch}":
                return sha
        raise GitError(f"Branch {branch} not found in {url}")

    def checkout(self, url: str, branch: str, auth: GitAuth, dest: Path, ca_file: Path | None = None) -> str:
        """Make `dest` hold exactly the tip of `branch`, fetching only that commit. Returns its commit.

        Every file in `dest` that is not in the commit is removed: it is the repository's, not ours.
        """
        dest.mkdir(parents=True, exist_ok=True)
        if not (dest / ".git").is_dir():
            self._run(["init", "--quiet"], auth, cwd=dest)
        # The URL is given each time and never stored as a remote, so changing it needs nothing here.
        fetch = ["fetch", "--quiet", "--depth", "1", "--no-tags", "--", url, f"refs/heads/{branch}"]
        self._run(fetch, auth, cwd=dest, ca_file=ca_file)
        self._run(["checkout", "--quiet", "--force", "--detach", "FETCH_HEAD"], auth, cwd=dest)
        self._run(["clean", "--quiet", "-ffdx"], auth, cwd=dest)
        return self.head(dest)

    def head(self, dest: Path) -> str | None:
        """The commit checked out in `dest`, or None when nothing is."""
        if not (dest / ".git").is_dir():
            return None
        try:
            return self._run(["rev-parse", "--verify", "--quiet", "HEAD"], GitAuth(), cwd=dest).strip() or None
        except GitError:
            return None

    def _run(self, args: list[str], auth: GitAuth, cwd: Path | None = None, ca_file: Path | None = None) -> str:
        env = {
            **os.environ,
            # Never wait for someone to type a password.
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            # Leave the host's and user's git configuration out of it.
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ALLOW_PROTOCOL": ":".join(self.allowed_protocols),
            **auth.env(),
        }
        tls = ["-c", f"http.sslCAInfo={ca_file}"] if ca_file else []
        command = ["git", "-c", "core.hooksPath=/dev/null", *tls, *auth.config(), *args]
        try:
            result = subprocess.run(
                command, cwd=cwd, env=env, capture_output=True, text=True, timeout=self.timeout, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {args[0]} timed out after {self.timeout:g}s") from exc
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip() or f"git {args[0]} exited with {result.returncode}"
            for secret in auth.secrets():
                if secret:
                    message = message.replace(secret, "***")
            raise GitError(message)
        return result.stdout
