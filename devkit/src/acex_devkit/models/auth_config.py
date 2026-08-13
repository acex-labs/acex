from pydantic import BaseModel


class AuthConfig(BaseModel):
    """Response from `GET /auth/config`.

    When `enabled` is False, `authority` and `client_id` are None.
    """

    enabled: bool
    authority: str | None = None
    client_id: str | None = None
