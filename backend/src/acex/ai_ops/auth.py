"""Credentials for AI providers that do not take a static API key."""

import asyncio

from .config import AzureClientSecretAuth


class AzureClientSecretToken:
    """Async API-key provider that returns a current Entra ID token.

    Passed to AsyncOpenAI as `api_key`; the SDK calls it before every request
    and sends the result as the bearer. The credential caches the token and
    renews it shortly before it expires, so most calls return from memory.
    get_token is blocking, hence the worker thread.
    """

    def __init__(self, auth: AzureClientSecretAuth):
        try:
            from azure.identity import ClientSecretCredential
        except ImportError as exc:
            raise RuntimeError(
                "AI provider auth 'azure_client_secret' needs azure-identity; install acex with the 'azure' extra"
            ) from exc
        self._credential = ClientSecretCredential(
            tenant_id=auth.tenant_id, client_id=auth.client_id, client_secret=auth.client_secret
        )
        self._scope = auth.scope

    async def __call__(self) -> str:
        token = await asyncio.to_thread(self._credential.get_token, self._scope)
        return token.token
