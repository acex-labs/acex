"""Tests for AI provider credentials that are not a static API key."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from acex.ai_ops.adapters import ResponsesAdapter
from acex.ai_ops.auth import AzureClientSecretToken
from acex.ai_ops.config import AIOpsSettings, AIProvider, AzureClientSecretAuth
from acex.ai_ops.endpoints import Endpoints

pytestmark = pytest.mark.anyio

AUTH = AzureClientSecretAuth(
    type="azure_client_secret", tenant_id="t", client_id="c", client_secret="s", scope="api://scope/.default"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def credential():
    """The ClientSecretCredential the token provider builds, with get_token stubbed."""
    instance = MagicMock()
    instance.get_token.return_value = SimpleNamespace(token="entra-token", expires_on=0)
    with patch("azure.identity.ClientSecretCredential", return_value=instance) as cls:
        yield cls, instance


class TestAzureClientSecretToken:
    async def test_returns_the_credentials_token_for_the_scope(self, credential):
        cls, instance = credential
        token = await AzureClientSecretToken(AUTH)()
        assert token == "entra-token"
        cls.assert_called_once_with(tenant_id="t", client_id="c", client_secret="s")
        instance.get_token.assert_called_once_with("api://scope/.default")

    async def test_asks_the_credential_on_every_call(self, credential):
        _, instance = credential
        provider = AzureClientSecretToken(AUTH)
        await provider()
        await provider()
        assert instance.get_token.call_count == 2


class TestEndpoints:
    @staticmethod
    def _endpoints(provider: AIProvider) -> Endpoints:
        return Endpoints(AIOpsSettings(providers={"p": provider}, chains={"default": "p/m"}))

    async def test_auth_provider_gets_a_token_callable(self, credential):
        endpoints = self._endpoints(AIProvider(base_url="https://apim/m/openai/v1/", auth=AUTH))
        client = endpoints.adapter(endpoints.settings.providers["p"], "m").client
        assert isinstance(client._api_key_provider, AzureClientSecretToken)
        await client._refresh_api_key()
        assert client.api_key == "entra-token"

    def test_api_key_provider_keeps_its_static_key(self):
        endpoints = self._endpoints(AIProvider(base_url="http://a", api_key="k"))
        client = endpoints.adapter(endpoints.settings.providers["p"], "m").client
        assert client.api_key == "k"
        assert client._api_key_provider is None

    def test_template_url_gives_each_model_its_client_and_one_token(self, credential):
        provider = AIProvider(base_url="https://apim/{model}/openai/v1/", api="responses", auth=AUTH, models="a,b")
        endpoints = self._endpoints(provider)
        provider = endpoints.settings.providers["p"]
        a, b = endpoints.adapter(provider, "a"), endpoints.adapter(provider, "b")
        assert isinstance(a, ResponsesAdapter)
        assert (str(a.client.base_url), str(b.client.base_url)) == (
            "https://apim/a/openai/v1/",
            "https://apim/b/openai/v1/",
        )
        assert a.client._api_key_provider is b.client._api_key_provider
        assert endpoints.adapter(provider, "a") is a
