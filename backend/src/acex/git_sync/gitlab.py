import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

_PER_PAGE = 100
#: A listing stops here and says that it was cut short.
_MAX_PAGES = 50


class GitHostError(RuntimeError):
    """The git host refused a request or could not be reached. The message can be shown as it is."""


@dataclass(frozen=True)
class OpenedMergeRequest:
    url: str
    number: int


def _trust(ca_file: Path | None) -> ssl.SSLContext:
    """The system's trusted CAs and, besides them, the certificates in `ca_file`."""
    context = ssl.create_default_context()
    if ca_file is not None:
        context.load_verify_locations(cafile=str(ca_file))
    return context


def _joined(said) -> str:
    return ", ".join(map(str, said)) if isinstance(said, list) else str(said)


class GitLab:
    def __init__(
        self,
        repository_url: str,
        token: str,
        *,
        ca_file: Path | None = None,
        timeout: float = 30,
        transport: httpx.BaseTransport | None = None,
    ):
        """`repository_url` is the HTTPS clone URL: its host is GitLab and its path names the project."""
        parts = urlsplit(repository_url)
        self.host = parts.netloc
        self.project = parts.path.strip("/").removesuffix(".git")
        if not self.project:
            raise GitHostError(f"{repository_url} names no project")
        self._origin = f"{parts.scheme}://{parts.netloc}"
        self._api = f"{self._origin}/api/v4/projects/{quote(self.project, safe='')}"
        self._token = token
        self._client = httpx.Client(
            headers={"PRIVATE-TOKEN": token},
            timeout=timeout,
            # A transport of its own, in the tests, makes its own connections.
            verify=_trust(ca_file) if transport is None else True,
            transport=transport,
        )

    def __enter__(self) -> "GitLab":
        return self

    def __exit__(self, *_) -> None:
        self._client.close()

    def tree(self, ref: str) -> tuple[list[str], list[str], bool]:
        """Every directory and every file on `ref`, and whether the listing was cut short."""
        directories: list[str] = []
        files: list[str] = []
        url = f"{self._api}/repository/tree"
        params = {"ref": ref, "recursive": "true", "per_page": str(_PER_PAGE), "pagination": "keyset"}
        for _ in range(_MAX_PAGES):
            response = self._send("GET", url, params=params)
            if response.status_code == 404 and "Tree Not Found" in self._said(response):
                raise GitHostError(f"GitLab at {self.host} has no branch {ref} in {self.project}")
            if response.status_code != 200:
                raise self._refused(response, "list the files")
            for entry in self._answer(response, list):
                (directories if entry.get("type") == "tree" else files).append(entry["path"])
            following = response.links.get("next", {}).get("url")
            if not following:
                return sorted(directories), sorted(files), False
            # The next page is asked for with the token, so only from the host that was asked first.
            if not following.startswith(f"{self._origin}/"):
                break
            url, params = following, None
        return sorted(directories), sorted(files), True

    def file_exists(self, path: str, ref: str) -> bool:
        response = self._send("HEAD", f"{self._api}/repository/files/{quote(path, safe='')}", params={"ref": ref})
        if response.status_code == 200:
            return True
        # Also the answer for a project the token cannot see; the commit that follows then says so.
        if response.status_code == 404:
            return False
        raise self._refused(response, "look for the file")

    def commit_file(
        self,
        *,
        branch: str,
        start_branch: str,
        path: str,
        content: str,
        message: str,
        replace: bool,
        author: tuple[str, str] | None = None,
    ) -> None:
        """Make `branch` from `start_branch` with one commit that adds the file, or changes it for `replace`.

        `author` is the name and the email address the commit is written in; left out, the token's own user.
        """
        payload = {
            "branch": branch,
            "start_branch": start_branch,
            "commit_message": message,
            "actions": [{"action": "update" if replace else "create", "file_path": path, "content": content}],
        }
        if author is not None:
            payload["author_name"], payload["author_email"] = author
        response = self._send("POST", f"{self._api}/repository/commits", json=payload)
        if not response.is_success:
            raise self._refused(response, "commit the file to a new branch")

    def open_merge_request(self, *, source: str, target: str, title: str, description: str) -> OpenedMergeRequest:
        payload = {
            "source_branch": source,
            "target_branch": target,
            "title": title,
            "description": description,
            "remove_source_branch": True,
        }
        response = self._send("POST", f"{self._api}/merge_requests", json=payload)
        if not response.is_success:
            raise self._refused(response, "open the merge request")
        opened = self._answer(response, dict)
        return OpenedMergeRequest(url=opened["web_url"], number=opened["iid"])

    def delete_branch(self, branch: str) -> None:
        """Take `branch` away again. Used to clean up, so a failure is not an error."""
        try:
            self._send("DELETE", f"{self._api}/repository/branches/{quote(branch, safe='')}")
        except GitHostError:
            pass

    def _send(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            return self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            reason = self._without_the_token(str(exc)) or type(exc).__name__
            raise GitHostError(f"Could not reach GitLab at {self.host}: {reason}") from exc

    def _answer(self, response: httpx.Response, kind: type):
        """The JSON of an answer. Another host than GitLab, or a proxy's login page, answers with something else."""
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, kind):
            raise GitHostError(f"{self.host} did not answer as GitLab does: merge requests are sent to GitLab only")
        return body

    def _refused(self, response: httpx.Response, action: str) -> GitHostError:
        status, said = response.status_code, self._said(response)
        if status == 401:
            return GitHostError(f"GitLab at {self.host} refused the token: it is wrong, revoked or has expired")
        if status == 403:
            return GitHostError(
                f"GitLab at {self.host} did not let the token {action}: "
                f"it needs the scope api and at least the role Developer in {self.project}"
            )
        if status == 404 and (not said or "Project Not Found" in said):
            return GitHostError(
                f"{self.host} has no GitLab project {self.project} that the token can see (404). "
                "Merge requests are sent to GitLab only"
            )
        return GitHostError(f"GitLab at {self.host} would not {action} ({status}){f': {said}' if said else ''}")

    def _said(self, response: httpx.Response) -> str:
        """GitLab's own words for a refusal, from the `message` or `error` of its JSON answer."""
        try:
            body = response.json()
        except ValueError:
            return ""
        if not isinstance(body, dict):
            return ""
        said = body.get("message") or body.get("error_description") or body.get("error") or ""
        if isinstance(said, dict):
            said = "; ".join(f"{field}: {_joined(why)}" for field, why in said.items())
        return self._without_the_token(_joined(said))[:300]

    def _without_the_token(self, text: str) -> str:
        return text.replace(self._token, "***") if self._token else text
