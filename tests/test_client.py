from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from infisical_mcp.client import (
    HttpRequest,
    HttpResponse,
    InfisicalClient,
    InfisicalConfigError,
    InfisicalSettings,
    render_env_lines,
    render_shell_exports,
    secret_pairs_from_response,
)


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def json_response(payload: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status=status, headers={}, body=json.dumps(payload).encode())


def test_request_uses_base_url_query_and_bearer_token() -> None:
    transport = FakeTransport([json_response({"ok": True})])
    client = InfisicalClient(
        InfisicalSettings(
            base_url="https://infisical.example.com",
            token="token-123",
            default_project_id="proj",
        ),
        transport=transport,
    )

    result = client.request(
        "GET",
        "/api/v4/secrets",
        query={"projectId": "proj", "recursive": True, "unset": None},
    )

    assert result == {"ok": True}
    request = transport.requests[0]
    assert request.method == "GET"
    assert request.url == (
        "https://infisical.example.com/api/v4/secrets?projectId=proj&recursive=true"
    )
    assert request.headers["Authorization"] == "Bearer token-123"
    assert request.body is None


def test_request_json_serializes_dict_query_values() -> None:
    transport = FakeTransport([json_response({"ok": True})])
    client = InfisicalClient(
        InfisicalSettings(
            base_url="https://infisical.example.com",
            token="token-123",
        ),
        transport=transport,
    )

    client.request("GET", "/api/example", query={"filter": {"key": "value"}})

    query = parse_qs(urlparse(transport.requests[0].url).query)
    assert query["filter"] == ['{"key":"value"}']


def test_universal_auth_logs_in_and_caches_access_token() -> None:
    transport = FakeTransport(
        [
            json_response({"accessToken": "runtime-token", "expiresIn": 300}),
            json_response({"secrets": []}),
        ]
    )
    client = InfisicalClient(
        InfisicalSettings(
            base_url="https://infisical.example.com",
            client_id="client",
            client_secret="secret",
            organization_slug="org",
            default_project_id="proj",
        ),
        transport=transport,
        now=lambda: 1000,
    )

    result = client.request("GET", "/api/v4/secrets")

    assert result == {"secrets": []}
    login_request = transport.requests[0]
    assert login_request.url == "https://infisical.example.com/api/v1/auth/universal-auth/login"
    assert "Authorization" not in login_request.headers
    assert json.loads(login_request.body or b"{}") == {
        "clientId": "client",
        "clientSecret": "secret",
        "organizationSlug": "org",
    }
    api_request = transport.requests[1]
    assert api_request.headers["Authorization"] == "Bearer runtime-token"


def test_missing_auth_raises_config_error() -> None:
    client = InfisicalClient(InfisicalSettings(base_url="https://infisical.example.com"))

    with pytest.raises(InfisicalConfigError):
        client.access_token()


def test_secret_pairs_from_common_response_shapes() -> None:
    response = {
        "secrets": [
            {"secretKey": "DATABASE_URL", "secretValue": "postgres://localhost/db"},
            {"secretName": "EMPTY", "secretValue": ""},
            {"name": "ALT", "value": "ok"},
        ]
    }

    assert secret_pairs_from_response(response) == [
        ("DATABASE_URL", "postgres://localhost/db"),
        ("EMPTY", ""),
        ("ALT", "ok"),
    ]


def test_render_env_and_shell_exports_quote_values() -> None:
    pairs = [("PLAIN", "abc"), ("WITH_SPACE", "hello world"), ("QUOTE", "it's ok")]

    assert render_env_lines(pairs) == 'PLAIN=abc\nQUOTE="it\'s ok"\nWITH_SPACE="hello world"\n'
    assert render_shell_exports(pairs) == (
        "export PLAIN='abc'\n"
        "export QUOTE='it'\"'\"'s ok'\n"
        "export WITH_SPACE='hello world'\n"
    )
