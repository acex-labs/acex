"""What a git host sends when a branch has a new commit, and how it is checked.

GitLab sends the secret as it is in `X-Gitlab-Token`. GitHub signs the body with it: `X-Hub-Signature-256` is
`sha256=` and the HMAC-SHA256 of the body. Either proves that the sender knows the secret of the repository. The
event says which ref moved; only a push to the branch the repository follows is worth a sync.
"""

import hashlib
import hmac
import json
from collections.abc import Mapping
from typing import NamedTuple

#: A push event with many commits is a few hundred kilobytes at most; anything larger is not one.
MAX_BODY_BYTES = 5_000_000

NO_COMMIT = "0" * 40


class Event(NamedTuple):
    """What the sender said happened: `kind` is `push`, `ping` or `other`, `ref` the ref of a push, `deleted` whether
    the push deleted it."""

    kind: str
    ref: str | None = None
    deleted: bool = False


def signed_by(secret: str, headers: Mapping[str, str], body: bytes) -> bool:
    """Whether the request carries the secret, GitLab's way or GitHub's. The comparisons take the same time whether or
    not they match."""
    token = headers.get("x-gitlab-token")
    if token is not None and hmac.compare_digest(token.encode(), secret.encode()):
        return True
    signature = headers.get("x-hub-signature-256")
    if signature is not None:
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature.encode(), expected.encode())
    return False


def event_of(headers: Mapping[str, str], body: bytes) -> Event:
    """The event of a request whose secret has been checked. A body that is not JSON is `other`."""
    github = headers.get("x-github-event")
    if github == "ping":
        return Event("ping")
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        return Event("other")
    if not isinstance(payload, dict):
        return Event("other")
    gitlab = headers.get("x-gitlab-event")
    if github == "push" or gitlab == "Push Hook" or payload.get("object_kind") == "push":
        ref = payload.get("ref")
        after = payload.get("after") or payload.get("checkout_sha")
        deleted = bool(payload.get("deleted")) or after == NO_COMMIT
        return Event("push", ref if isinstance(ref, str) else None, deleted)
    return Event("other")
