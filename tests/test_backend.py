import pytest

from meetdub.backend import azure_backend, openai_backend


def test_openai_backend_url_and_auth():
    b = openai_backend("sk-test")
    assert b.name == "openai"
    assert "api.openai.com" in b.ws_url
    assert "model=gpt-realtime-translate" in b.ws_url
    assert b.headers["Authorization"] == "Bearer sk-test"


def test_azure_ga_backend_with_api_key():
    b = azure_backend(
        endpoint="my-resource.openai.azure.com",
        deployment="my-translate",
        api_key="abc123",
    )
    assert b.name == "azure"
    assert b.ws_url.startswith("wss://my-resource.openai.azure.com/")
    assert "/openai/v1/realtime/translations" in b.ws_url
    assert "model=my-translate" in b.ws_url
    assert b.headers == {"api-key": "abc123"}


def test_azure_strips_scheme_and_trailing_slash():
    b = azure_backend(
        endpoint="https://my-resource.openai.azure.com/",
        deployment="d",
        api_key="k",
    )
    # No double slash, no scheme in host
    assert "://my-resource.openai.azure.com/openai/" in b.ws_url
    assert b.ws_url.count("://") == 1


def test_azure_preview_uses_api_version_and_deployment_qs():
    b = azure_backend(
        endpoint="r.openai.azure.com",
        deployment="d",
        api_key="k",
        api_version="2025-04-01-preview",
    )
    assert "/openai/realtime/translations" in b.ws_url
    assert "api-version=2025-04-01-preview" in b.ws_url
    assert "deployment=d" in b.ws_url
    # Preview shape uses deployment=, not model=
    assert "model=" not in b.ws_url


def test_azure_aad_token_takes_precedence():
    b = azure_backend(
        endpoint="r.openai.azure.com",
        deployment="d",
        aad_token="entra-token",
    )
    assert b.headers == {"Authorization": "Bearer entra-token"}


def test_azure_custom_path_override():
    b = azure_backend(
        endpoint="r.openai.azure.com",
        deployment="d",
        api_key="k",
        path="/openai/v1/realtime",
    )
    assert b.ws_url.endswith("openai/v1/realtime?model=d")


def test_azure_requires_endpoint():
    with pytest.raises(ValueError, match="endpoint is required"):
        azure_backend(endpoint="", deployment="d", api_key="k")


def test_azure_requires_deployment():
    with pytest.raises(ValueError, match="deployment name is required"):
        azure_backend(endpoint="r.openai.azure.com", deployment="", api_key="k")


def test_azure_requires_some_auth():
    with pytest.raises(ValueError, match="api_key or aad_token"):
        azure_backend(endpoint="r.openai.azure.com", deployment="d")
