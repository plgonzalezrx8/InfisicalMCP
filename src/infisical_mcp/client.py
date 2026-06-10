from __future__ import annotations

import json
import os
import ssl
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


JsonObject = dict[str, Any]


class InfisicalConfigError(RuntimeError):
    """Raised when required Infisical runtime configuration is missing."""


class InfisicalAPIError(RuntimeError):
    """Raised when Infisical returns an HTTP or transport error."""

    def __init__(self, message: str, *, status: int | None = None, payload: Any = None) -> None:
        self.status = status
        self.payload = payload
        super().__init__(message)


@dataclass(frozen=True)
class InfisicalSettings:
    base_url: str
    token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    organization_slug: str | None = None
    default_project_id: str | None = None
    default_environment: str = "dev"
    default_secret_path: str = "/"
    timeout_seconds: float = 30.0
    verify_tls: bool = True

    @classmethod
    def from_env(cls) -> "InfisicalSettings":
        token = _empty_to_none(os.getenv("INFISICAL_TOKEN")) or _empty_to_none(
            os.getenv("INFISICAL_API_KEY")
        )
        return cls(
            base_url=os.getenv(
                "INFISICAL_BASE_URL",
                "https://infisical-bfi.blueforceinnovations.com",
            ),
            token=token,
            client_id=_empty_to_none(os.getenv("INFISICAL_CLIENT_ID")),
            client_secret=_empty_to_none(os.getenv("INFISICAL_CLIENT_SECRET")),
            organization_slug=_empty_to_none(os.getenv("INFISICAL_ORGANIZATION_SLUG")),
            default_project_id=_empty_to_none(os.getenv("INFISICAL_PROJECT_ID")),
            default_environment=os.getenv("INFISICAL_ENVIRONMENT", "dev"),
            default_secret_path=os.getenv("INFISICAL_SECRET_PATH", "/"),
            timeout_seconds=float(os.getenv("INFISICAL_TIMEOUT_SECONDS", "30")),
            verify_tls=_parse_bool(os.getenv("INFISICAL_VERIFY_TLS", "true")),
        )

    @property
    def auth_mode(self) -> str:
        if self.token:
            return "token"
        if self.client_id and self.client_secret:
            return "universal_auth"
        return "unconfigured"


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None
    timeout_seconds: float
    verify_tls: bool


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class Transport(Protocol):
    def __call__(self, request: HttpRequest) -> HttpResponse: ...


class UrllibTransport:
    def __call__(self, request: HttpRequest) -> HttpResponse:
        ssl_context = None if request.verify_tls else ssl._create_unverified_context()
        urllib_request = Request(
            request.url,
            data=request.body,
            headers=request.headers,
            method=request.method,
        )
        try:
            with urlopen(
                urllib_request,
                timeout=request.timeout_seconds,
                context=ssl_context,
            ) as response:
                return HttpResponse(
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except HTTPError as exc:
            raise InfisicalAPIError(
                f"Infisical API returned HTTP {exc.code}",
                status=exc.code,
                payload=_parse_json_bytes(exc.read()),
            ) from exc
        except URLError as exc:
            raise InfisicalAPIError(f"Infisical API request failed: {exc.reason}") from exc


class InfisicalClient:
    def __init__(
        self,
        settings: InfisicalSettings | None = None,
        *,
        transport: Transport | None = None,
        now: Any | None = None,
    ) -> None:
        self.settings = settings or InfisicalSettings.from_env()
        self.transport = transport or UrllibTransport()
        self._now = now or time.time
        self._cached_token: str | None = None
        self._cached_token_expires_at = 0.0

    def request(
        self,
        method: str,
        path: str,
        *,
        query: JsonObject | None = None,
        json_body: JsonObject | None = None,
        auth: bool = True,
    ) -> Any:
        url = self._url(path, query)
        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "infisical-mcp/0.1.0",
        }
        if json_body is not None:
            body = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth:
            headers["Authorization"] = f"Bearer {self.access_token()}"

        response = self.transport(
            HttpRequest(
                method=method.upper(),
                url=url,
                headers=headers,
                body=body,
                timeout_seconds=self.settings.timeout_seconds,
                verify_tls=self.settings.verify_tls,
            )
        )
        if response.status >= 400:
            raise InfisicalAPIError(
                f"Infisical API returned HTTP {response.status}",
                status=response.status,
                payload=_parse_json_bytes(response.body),
            )
        if not response.body:
            return {"ok": True, "status": response.status}
        return _parse_json_bytes(response.body)

    def access_token(self) -> str:
        if self.settings.token:
            return self.settings.token
        if not self.settings.client_id or not self.settings.client_secret:
            raise InfisicalConfigError(
                "Set INFISICAL_TOKEN/INFISICAL_API_KEY or "
                "INFISICAL_CLIENT_ID and INFISICAL_CLIENT_SECRET."
            )
        if self._cached_token and self._cached_token_expires_at > self._now() + 30:
            return self._cached_token
        payload: JsonObject = {
            "clientId": self.settings.client_id,
            "clientSecret": self.settings.client_secret,
        }
        if self.settings.organization_slug:
            payload["organizationSlug"] = self.settings.organization_slug
        response = self.request(
            "POST",
            "/api/v1/auth/universal-auth/login",
            json_body=payload,
            auth=False,
        )
        token = response.get("accessToken")
        if not isinstance(token, str) or not token:
            raise InfisicalAPIError("Universal Auth response did not include accessToken")
        expires_in = response.get("expiresIn", 300)
        try:
            expires_seconds = int(expires_in)
        except (TypeError, ValueError):
            expires_seconds = 300
        self._cached_token = token
        self._cached_token_expires_at = self._now() + max(expires_seconds, 60)
        return token

    def default_project_id(self, project_id: str | None = None) -> str:
        value = _empty_to_none(project_id) or self.settings.default_project_id
        if not value:
            raise InfisicalConfigError("Provide project_id or set INFISICAL_PROJECT_ID.")
        return value

    def default_environment(self, environment: str | None = None) -> str:
        return _empty_to_none(environment) or self.settings.default_environment

    def default_secret_path(self, secret_path: str | None = None) -> str:
        return _empty_to_none(secret_path) or self.settings.default_secret_path

    def _url(self, path: str, query: JsonObject | None = None) -> str:
        base = self.settings.base_url.rstrip("/") + "/"
        clean_path = path.lstrip("/")
        url = urljoin(base, clean_path)
        params = _clean_params(query or {})
        if params:
            return f"{url}?{urlencode(params, doseq=True)}"
        return url


def compact_payload(data: JsonObject) -> JsonObject:
    return {key: value for key, value in data.items() if value is not None}


def secret_pairs_from_response(response: Any) -> list[tuple[str, str]]:
    secrets = _extract_secret_list(response)
    pairs: list[tuple[str, str]] = []
    for secret in secrets:
        if not isinstance(secret, dict):
            continue
        key = (
            secret.get("secretKey")
            or secret.get("secretName")
            or secret.get("key")
            or secret.get("name")
        )
        value = (
            secret.get("secretValue")
            or secret.get("value")
            or secret.get("secretValueHidden")
            or ""
        )
        if isinstance(key, str) and key:
            pairs.append((key, "" if value is None else str(value)))
    return pairs


def render_env_lines(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"{key}={_dotenv_quote(value)}" for key, value in sorted(pairs)) + "\n"


def render_shell_exports(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"export {key}={_shell_quote(value)}" for key, value in sorted(pairs)) + "\n"


def _extract_secret_list(response: Any) -> list[Any]:
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return []
    for key in ("secrets", "items", "data"):
        value = response.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_secret_list(value)
            if nested:
                return nested
    return []


def _dotenv_quote(value: str) -> str:
    if value == "":
        return '""'
    if all(ch not in value for ch in " \t\n\r#='\"\\"):
        return value
    escaped = value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
    return f'"{escaped}"'


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _parse_bool(value: str | None) -> bool:
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _clean_params(values: JsonObject) -> JsonObject:
    params: JsonObject = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, bool):
            params[key] = "true" if value else "false"
        elif isinstance(value, (dict, list, tuple)) and key == "metadataFilter":
            params[key] = json.dumps(value, separators=(",", ":"))
        else:
            params[key] = value
    return params


def _parse_json_bytes(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}

