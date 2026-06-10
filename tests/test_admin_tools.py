from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

import infisical_mcp.server as server
from infisical_mcp.client import HttpRequest, HttpResponse, InfisicalClient, InfisicalSettings


class FakeTransport:
    def __init__(self, responses: list[HttpResponse] | None = None) -> None:
        if responses is None:
            responses = [json_response({"ok": True}) for _ in range(100)]
        self.responses = list(responses)
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def json_response(payload: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status=status, headers={}, body=json.dumps(payload).encode())


def install_fake_client(monkeypatch, transport: FakeTransport) -> None:
    client = InfisicalClient(
        InfisicalSettings(
            base_url="https://infisical.example.com",
            token="token-123",
            default_project_id="project-123",
            default_environment="dev",
            default_secret_path="/app",
        ),
        transport=transport,
    )
    monkeypatch.setattr(server, "get_client", lambda: client)


def body(request: HttpRequest) -> dict:
    return json.loads(request.body or b"{}")


def test_fake_transport_respects_explicit_empty_response_list() -> None:
    transport = FakeTransport([])

    with pytest.raises(IndexError):
        transport(
            HttpRequest(
                method="GET",
                url="https://infisical.example.com/api/v1/projects",
                headers={},
                body=None,
                timeout_seconds=30,
                verify_tls=True,
            )
        )


def test_identity_tools_build_organization_identity_requests(monkeypatch) -> None:
    transport = FakeTransport()
    install_fake_client(monkeypatch, transport)

    server.list_identities(org_id="org-123")
    server.get_identity(identity_id="identity-123")
    server.create_identity(
        name="deploy-bot",
        organization_id="org-123",
        role="member",
        has_delete_protection=True,
        metadata=[{"key": "owner", "value": "platform"}],
    )
    server.update_identity(identity_id="identity-123", name="renamed", role="admin")
    server.delete_identity(identity_id="identity-123")

    assert transport.requests[0].method == "GET"
    assert transport.requests[0].url == "https://infisical.example.com/api/v1/identities?orgId=org-123"
    assert transport.requests[1].method == "GET"
    assert transport.requests[1].url == "https://infisical.example.com/api/v1/identities/identity-123"
    assert transport.requests[2].method == "POST"
    assert transport.requests[2].url == "https://infisical.example.com/api/v1/identities"
    assert body(transport.requests[2]) == {
        "name": "deploy-bot",
        "organizationId": "org-123",
        "role": "member",
        "hasDeleteProtection": True,
        "metadata": [{"key": "owner", "value": "platform"}],
    }
    assert transport.requests[3].method == "PATCH"
    assert transport.requests[3].url == "https://infisical.example.com/api/v1/identities/identity-123"
    assert body(transport.requests[3]) == {"name": "renamed", "role": "admin"}
    assert transport.requests[4].method == "DELETE"
    assert transport.requests[4].url == "https://infisical.example.com/api/v1/identities/identity-123"


def test_project_identity_tools_build_requests(monkeypatch) -> None:
    transport = FakeTransport()
    install_fake_client(monkeypatch, transport)

    server.list_project_identities(search="deploy")
    server.get_project_identity("identity-123")
    server.create_project_identity(
        name="project-bot",
        has_delete_protection=True,
        metadata=[{"key": "owner", "value": "platform"}],
    )
    server.update_project_identity("identity-123", name="project-bot-renamed")
    server.delete_project_identity("identity-123")

    assert transport.requests[0].method == "GET"
    assert transport.requests[0].url == (
        "https://infisical.example.com/api/v1/projects/project-123/identities"
        "?offset=0&limit=20&search=deploy"
    )
    assert transport.requests[1].method == "GET"
    assert transport.requests[1].url.endswith(
        "/api/v1/projects/project-123/identities/identity-123"
    )
    assert transport.requests[2].method == "POST"
    assert transport.requests[2].url.endswith("/api/v1/projects/project-123/identities")
    assert body(transport.requests[2]) == {
        "name": "project-bot",
        "hasDeleteProtection": True,
        "metadata": [{"key": "owner", "value": "platform"}],
    }
    assert transport.requests[3].method == "PATCH"
    assert transport.requests[3].url.endswith(
        "/api/v1/projects/project-123/identities/identity-123"
    )
    assert body(transport.requests[3]) == {"name": "project-bot-renamed"}
    assert transport.requests[4].method == "DELETE"
    assert transport.requests[4].url.endswith(
        "/api/v1/projects/project-123/identities/identity-123"
    )


def test_project_membership_tools_build_user_and_identity_membership_requests(monkeypatch) -> None:
    transport = FakeTransport()
    install_fake_client(monkeypatch, transport)

    roles = [{"role": "viewer", "isTemporary": False}]
    server.list_project_user_memberships()
    server.invite_project_users(emails=["ops@example.com"], usernames=[], role_slugs=["viewer"])
    server.invite_project_users(emails=["member@example.com"], role_slugs=[])
    server.update_project_user_membership("membership-123", roles=roles)
    server.remove_project_users(usernames=["old-user"])
    server.get_project_user_by_username("ops@example.com")
    server.list_project_identity_memberships(roles=["viewer"], search="bot")
    server.create_project_identity_membership("identity-123", roles=roles)
    server.update_project_identity_membership("identity-123", roles=roles)
    server.delete_project_identity_membership("identity-123")

    assert transport.requests[0].url == (
        "https://infisical.example.com/api/v1/projects/project-123/memberships"
    )
    assert transport.requests[1].method == "POST"
    assert body(transport.requests[1]) == {
        "emails": ["ops@example.com"],
        "usernames": [],
        "roleSlugs": ["viewer"],
    }
    assert transport.requests[2].method == "POST"
    assert body(transport.requests[2]) == {"emails": ["member@example.com"]}
    assert transport.requests[3].method == "PATCH"
    assert transport.requests[3].url.endswith("/api/v1/projects/project-123/memberships/membership-123")
    assert body(transport.requests[3]) == {"roles": roles}
    assert transport.requests[4].method == "DELETE"
    assert body(transport.requests[4]) == {"usernames": ["old-user"]}
    assert transport.requests[5].method == "POST"
    assert transport.requests[5].url.endswith("/api/v1/projects/project-123/memberships/details")
    assert body(transport.requests[5]) == {"username": "ops@example.com"}
    assert transport.requests[6].method == "GET"
    assert transport.requests[6].url == (
        "https://infisical.example.com/api/v1/projects/project-123/memberships/identities"
        "?offset=0&limit=20&identityName=bot&roles=viewer"
    )
    assert transport.requests[7].method == "POST"
    assert transport.requests[7].url.endswith(
        "/api/v1/projects/project-123/memberships/identities/identity-123"
    )
    assert body(transport.requests[7]) == {"roles": roles}
    assert transport.requests[8].method == "PATCH"
    assert transport.requests[8].url.endswith(
        "/api/v1/projects/project-123/memberships/identities/identity-123"
    )
    assert body(transport.requests[8]) == {"roles": roles}
    assert transport.requests[9].method == "DELETE"


def test_membership_role_tools_reject_empty_roles(monkeypatch) -> None:
    transport = FakeTransport()
    install_fake_client(monkeypatch, transport)

    with pytest.raises(ValueError, match="roles must include at least one role assignment"):
        server.update_project_user_membership("membership-123", roles=[])

    with pytest.raises(ValueError, match="roles must include at least one role assignment"):
        server.create_project_identity_membership("identity-123", roles=[])

    with pytest.raises(ValueError, match="roles must include at least one role assignment"):
        server.update_project_identity_membership("identity-123", roles=[])

    assert transport.requests == []


def test_project_roles_audit_logs_and_secret_imports_requests(monkeypatch) -> None:
    transport = FakeTransport()
    install_fake_client(monkeypatch, transport)

    permissions = [{"subject": "secrets", "action": ["read"], "conditions": {"environment": "dev"}}]
    server.create_project_role(slug="ci", name="CI", permissions=permissions)
    server.update_project_role("role-123", name="CI Updated", permissions=permissions)
    server.get_project_role_by_slug("ci")
    server.delete_project_role("role-123")
    server.export_audit_logs(
        project_id="project-123",
        environment="dev",
        event_type=["get-secret", "update-secret"],
        actor_type="identity",
        actor="identity-123",
        event_metadata={"ipAddress": "127.0.0.1"},
    )
    server.list_secret_imports()
    server.create_secret_import(
        import_environment="prod",
        import_path="/shared",
        is_replication=True,
    )
    server.update_secret_import("import-123", import_environment="stage", position=2)
    server.delete_secret_import("import-123")

    assert transport.requests[0].method == "POST"
    assert transport.requests[0].url.endswith("/api/v1/projects/project-123/roles")
    assert body(transport.requests[0]) == {"slug": "ci", "name": "CI", "permissions": permissions}
    assert transport.requests[1].method == "PATCH"
    assert body(transport.requests[1]) == {"name": "CI Updated", "permissions": permissions}
    assert transport.requests[2].method == "GET"
    assert transport.requests[2].url.endswith("/api/v1/projects/project-123/roles/slug/ci")
    assert transport.requests[3].method == "DELETE"
    assert transport.requests[4].method == "GET"
    assert transport.requests[4].url == (
        "https://infisical.example.com/api/v1/organization/audit-logs"
        "?projectId=project-123&environment=dev&actorType=identity&eventType=get-secret"
        "&eventType=update-secret&eventMetadata=ipAddress%3D127.0.0.1&actor=identity-123"
    )
    assert transport.requests[5].url == (
        "https://infisical.example.com/api/v2/secret-imports"
        "?projectId=project-123&environment=dev&path=%2Fapp"
    )
    assert transport.requests[6].method == "POST"
    assert body(transport.requests[6]) == {
        "projectId": "project-123",
        "environment": "dev",
        "path": "/app",
        "import": {
            "environment": "prod",
            "path": "/shared",
        },
        "isReplication": True,
    }
    assert transport.requests[7].method == "PATCH"
    assert body(transport.requests[7]) == {
        "projectId": "project-123",
        "environment": "dev",
        "path": "/app",
        "import": {"environment": "stage", "position": 2},
    }
    assert transport.requests[8].method == "DELETE"
    assert body(transport.requests[8]) == {
        "projectId": "project-123",
        "environment": "dev",
        "path": "/app",
    }


def test_audit_event_metadata_uses_documented_key_value_format(monkeypatch) -> None:
    transport = FakeTransport()
    install_fake_client(monkeypatch, transport)

    server.export_audit_logs(event_metadata={"ipAddress": "127.0.0.1", "secretPath": "/app"})

    query = parse_qs(urlparse(transport.requests[0].url).query)
    assert query["eventMetadata"] == ["ipAddress=127.0.0.1,secretPath=/app"]


def test_admin_client_serializes_dict_query_values(monkeypatch) -> None:
    transport = FakeTransport()
    install_fake_client(monkeypatch, transport)

    client = server.get_client()
    client.request(
        "GET",
        "/api/v1/example",
        query={"metadataFilter": {"ipAddress": "127.0.0.1"}},
    )

    query = parse_qs(urlparse(transport.requests[0].url).query)
    assert query["metadataFilter"] == ['{"ipAddress":"127.0.0.1"}']


def test_org_memberships_identity_privileges_and_secret_import_helpers(monkeypatch) -> None:
    transport = FakeTransport()
    install_fake_client(monkeypatch, transport)

    permissions = [{"subject": "secrets", "action": ["read"]}]
    privilege_type = {"kind": "permanent"}
    roles = [{"role": "viewer", "isTemporary": False}]

    server.list_organization_user_memberships("org-123")
    server.update_organization_user_membership(
        "org-123",
        "member-123",
        role="admin",
        is_active=True,
    )
    server.remove_organization_user_membership("org-123", "member-123")
    server.remove_organization_user_memberships("org-123", membership_ids=["member-456"])
    server.list_organization_identity_memberships("org-123", search="ci")
    server.create_project_identity_membership("identity-123", roles=roles)
    server.create_identity_project_additional_privilege(
        identity_id="identity-123",
        permissions=permissions,
        privilege_type=privilege_type,
        slug="ci-read",
    )
    server.get_identity_project_additional_privilege("privilege-123")
    server.update_identity_project_additional_privilege(
        "privilege-123",
        permissions=permissions,
        slug="ci-read-updated",
        privilege_type={"kind": "temporary", "expiresAt": "2026-06-11T00:00:00Z"},
    )
    server.delete_identity_project_additional_privilege("privilege-123")

    assert transport.requests[0].method == "GET"
    assert transport.requests[0].url == (
        "https://infisical.example.com/api/v2/organizations/org-123/memberships"
    )
    assert transport.requests[1].method == "PATCH"
    assert transport.requests[1].url.endswith(
        "/api/v2/organizations/org-123/memberships/member-123"
    )
    assert body(transport.requests[1]) == {"role": "admin", "isActive": True}
    assert transport.requests[2].method == "DELETE"
    assert transport.requests[2].url.endswith("/api/v2/organizations/org-123/memberships/member-123")
    assert transport.requests[3].method == "DELETE"
    assert body(transport.requests[3]) == {"membershipIds": ["member-456"]}
    assert transport.requests[4].method == "GET"
    assert transport.requests[4].url == (
        "https://infisical.example.com/api/v2/organizations/org-123/identity-memberships"
        "?offset=0&limit=100&search=ci"
    )
    assert transport.requests[5].method == "POST"
    assert transport.requests[5].url.endswith(
        "/api/v1/projects/project-123/memberships/identities/identity-123"
    )
    assert body(transport.requests[5]) == {"roles": roles}
    assert transport.requests[6].method == "POST"
    assert transport.requests[6].url.endswith("/api/v2/identity-project-additional-privilege")
    assert body(transport.requests[6]) == {
        "identityId": "identity-123",
        "projectId": "project-123",
        "permissions": permissions,
        "type": privilege_type,
        "slug": "ci-read",
    }
    assert transport.requests[7].method == "GET"
    assert transport.requests[7].url.endswith(
        "/api/v2/identity-project-additional-privilege/privilege-123"
    )
    assert transport.requests[8].method == "PATCH"
    assert body(transport.requests[8]) == {
        "permissions": permissions,
        "slug": "ci-read-updated",
        "type": {"kind": "temporary", "expiresAt": "2026-06-11T00:00:00Z"},
    }
    assert transport.requests[9].method == "DELETE"
