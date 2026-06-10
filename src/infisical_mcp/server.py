from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from fastmcp import FastMCP

from .client import (
    InfisicalClient,
    InfisicalConfigError,
    InfisicalSettings,
    compact_payload,
    render_env_lines,
    render_shell_exports as render_shell_export_lines,
    secret_pairs_from_response,
)


READ_ONLY = {"readOnlyHint": True, "openWorldHint": True}
MUTATING = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True}


def get_client() -> InfisicalClient:
    return InfisicalClient()


mcp = FastMCP(
    "Infisical MCP",
    instructions=(
        "Manage Infisical projects, environments, folders, and static secrets. "
        "Use render_env_file or render_shell_exports when a project needs secrets."
    ),
)


@mcp.tool(annotations=READ_ONLY)
def server_config() -> dict[str, Any]:
    """Show non-secret runtime configuration for this Infisical MCP server."""
    settings = InfisicalSettings.from_env()
    return {
        "base_url": settings.base_url,
        "auth_mode": settings.auth_mode,
        "default_project_id_set": bool(settings.default_project_id),
        "default_environment": settings.default_environment,
        "default_secret_path": settings.default_secret_path,
        "verify_tls": settings.verify_tls,
    }


@mcp.tool(annotations=READ_ONLY)
def list_projects(include_roles: bool = False, project_type: str | None = None) -> Any:
    """List Infisical projects visible to the configured identity."""
    return get_client().request(
        "GET",
        "/api/v1/projects",
        query={"includeRoles": include_roles, "type": project_type},
    )


@mcp.tool(annotations=READ_ONLY)
def get_project(project_id: str | None = None, slug: str | None = None) -> Any:
    """Get a project by ID or slug."""
    if project_id:
        return get_client().request("GET", f"/api/v1/projects/{quote(project_id, safe='')}")
    if slug:
        return get_client().request("GET", f"/api/v1/projects/slug/{quote(slug, safe='')}")
    raise InfisicalConfigError("Provide project_id or slug.")


@mcp.tool(annotations=MUTATING)
def create_project(
    project_name: str,
    project_description: str | None = None,
    slug: str | None = None,
    should_create_default_envs: bool | None = True,
    project_type: str | None = None,
    has_delete_protection: bool | None = None,
) -> Any:
    """Create an Infisical project."""
    return get_client().request(
        "POST",
        "/api/v1/projects",
        json_body=compact_payload(
            {
                "projectName": project_name,
                "projectDescription": project_description,
                "slug": slug,
                "shouldCreateDefaultEnvs": should_create_default_envs,
                "type": project_type,
                "hasDeleteProtection": has_delete_protection,
            }
        ),
    )


@mcp.tool(annotations=MUTATING)
def update_project(
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    slug: str | None = None,
    has_delete_protection: bool | None = None,
) -> Any:
    """Update basic Infisical project metadata."""
    return get_client().request(
        "PATCH",
        f"/api/v1/projects/{quote(project_id, safe='')}",
        json_body=compact_payload(
            {
                "name": name,
                "description": description,
                "slug": slug,
                "hasDeleteProtection": has_delete_protection,
            }
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
def delete_project(project_id: str) -> Any:
    """Delete an Infisical project."""
    return get_client().request("DELETE", f"/api/v1/projects/{quote(project_id, safe='')}")


@mcp.tool(annotations=READ_ONLY)
def list_environments(project_id: str | None = None, slug: str | None = None) -> dict[str, Any]:
    """List environments from a project response."""
    project = get_project(project_id=project_id, slug=slug)
    project_payload = project.get("project", project) if isinstance(project, dict) else project
    environments = []
    if isinstance(project_payload, dict):
        environments = project_payload.get("environments", [])
    return {"project": project_payload, "environments": environments}


@mcp.tool(annotations=MUTATING)
def create_environment(
    name: str,
    slug: str,
    project_id: str | None = None,
    position: int | None = None,
) -> Any:
    """Create an environment in a project."""
    client = get_client()
    project_id = client.default_project_id(project_id)
    return client.request(
        "POST",
        f"/api/v1/projects/{quote(project_id, safe='')}/environments",
        json_body=compact_payload({"name": name, "slug": slug, "position": position}),
    )


@mcp.tool(annotations=MUTATING)
def update_environment(
    environment_id: str,
    project_id: str | None = None,
    name: str | None = None,
    slug: str | None = None,
    position: int | None = None,
) -> Any:
    """Update an environment by ID."""
    client = get_client()
    project_id = client.default_project_id(project_id)
    return client.request(
        "PATCH",
        (
            f"/api/v1/projects/{quote(project_id, safe='')}/environments/"
            f"{quote(environment_id, safe='')}"
        ),
        json_body=compact_payload({"name": name, "slug": slug, "position": position}),
    )


@mcp.tool(annotations=DESTRUCTIVE)
def delete_environment(
    environment_id: str,
    project_id: str | None = None,
    hard_delete: bool | None = None,
) -> Any:
    """Delete an environment by ID."""
    client = get_client()
    project_id = client.default_project_id(project_id)
    return client.request(
        "DELETE",
        (
            f"/api/v1/projects/{quote(project_id, safe='')}/environments/"
            f"{quote(environment_id, safe='')}"
        ),
        query={"hardDelete": hard_delete},
    )


@mcp.tool(annotations=READ_ONLY)
def list_folders(
    project_id: str | None = None,
    environment: str | None = None,
    path: str | None = None,
    recursive: bool = False,
    last_secret_modified: bool | None = None,
) -> Any:
    """List Infisical folders in an environment and path."""
    client = get_client()
    return client.request(
        "GET",
        "/api/v2/folders",
        query={
            "projectId": client.default_project_id(project_id),
            "environment": client.default_environment(environment),
            "path": client.default_secret_path(path),
            "recursive": recursive,
            "lastSecretModified": last_secret_modified,
        },
    )


@mcp.tool(annotations=MUTATING)
def create_folder(
    name: str,
    project_id: str | None = None,
    environment: str | None = None,
    path: str | None = None,
    description: str | None = None,
) -> Any:
    """Create an Infisical folder."""
    client = get_client()
    return client.request(
        "POST",
        "/api/v2/folders",
        json_body=compact_payload(
            {
                "projectId": client.default_project_id(project_id),
                "environment": client.default_environment(environment),
                "name": name,
                "path": client.default_secret_path(path),
                "description": description,
            }
        ),
    )


@mcp.tool(annotations=MUTATING)
def update_folder(
    folder_id: str,
    name: str,
    project_id: str | None = None,
    environment: str | None = None,
    path: str | None = None,
    description: str | None = None,
) -> Any:
    """Update an Infisical folder by ID."""
    client = get_client()
    return client.request(
        "PATCH",
        f"/api/v2/folders/{quote(folder_id, safe='')}",
        json_body=compact_payload(
            {
                "projectId": client.default_project_id(project_id),
                "environment": client.default_environment(environment),
                "name": name,
                "path": client.default_secret_path(path),
                "description": description,
            }
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
def delete_folder(
    folder_id_or_name: str,
    project_id: str | None = None,
    environment: str | None = None,
    path: str | None = None,
    force_delete: bool = False,
) -> Any:
    """Delete an Infisical folder by ID or name."""
    client = get_client()
    return client.request(
        "DELETE",
        f"/api/v2/folders/{quote(folder_id_or_name, safe='')}",
        json_body={
            "projectId": client.default_project_id(project_id),
            "environment": client.default_environment(environment),
            "path": client.default_secret_path(path),
            "forceDelete": force_delete,
        },
    )


@mcp.tool(annotations=READ_ONLY)
def list_secrets(
    project_id: str | None = None,
    environment: str | None = None,
    secret_path: str | None = None,
    recursive: bool = False,
    view_secret_value: bool = False,
    expand_secret_references: bool = False,
    include_imports: bool = False,
    include_personal_overrides: bool = False,
) -> Any:
    """List static secrets in an Infisical project environment."""
    client = get_client()
    return client.request(
        "GET",
        "/api/v4/secrets",
        query={
            "projectId": client.default_project_id(project_id),
            "environment": client.default_environment(environment),
            "secretPath": client.default_secret_path(secret_path),
            "recursive": recursive,
            "viewSecretValue": view_secret_value,
            "expandSecretReferences": expand_secret_references,
            "includeImports": include_imports,
            "includePersonalOverrides": include_personal_overrides,
        },
    )


@mcp.tool(annotations=READ_ONLY)
def get_secret(
    secret_name: str,
    project_id: str | None = None,
    environment: str | None = None,
    secret_path: str | None = None,
    view_secret_value: bool = True,
    expand_secret_references: bool = False,
) -> Any:
    """Get one static secret by name."""
    client = get_client()
    return client.request(
        "GET",
        f"/api/v4/secrets/{quote(secret_name, safe='')}",
        query={
            "projectId": client.default_project_id(project_id),
            "environment": client.default_environment(environment),
            "secretPath": client.default_secret_path(secret_path),
            "viewSecretValue": view_secret_value,
            "expandSecretReferences": expand_secret_references,
        },
    )


@mcp.tool(annotations=MUTATING)
def create_secret(
    secret_name: str,
    secret_value: str,
    project_id: str | None = None,
    environment: str | None = None,
    secret_path: str | None = None,
    secret_type: str | None = "shared",
    secret_comment: str | None = None,
    skip_multiline_encoding: bool | None = None,
) -> Any:
    """Create a static secret."""
    client = get_client()
    return client.request(
        "POST",
        f"/api/v4/secrets/{quote(secret_name, safe='')}",
        json_body=compact_payload(
            {
                "projectId": client.default_project_id(project_id),
                "environment": client.default_environment(environment),
                "secretPath": client.default_secret_path(secret_path),
                "secretValue": secret_value,
                "type": secret_type,
                "secretComment": secret_comment,
                "skipMultilineEncoding": skip_multiline_encoding,
            }
        ),
    )


@mcp.tool(annotations=MUTATING)
def update_secret(
    secret_name: str,
    project_id: str | None = None,
    environment: str | None = None,
    secret_path: str | None = None,
    secret_value: str | None = None,
    new_secret_name: str | None = None,
    secret_type: str | None = "shared",
    secret_comment: str | None = None,
) -> Any:
    """Update or rename a static secret."""
    client = get_client()
    return client.request(
        "PATCH",
        f"/api/v4/secrets/{quote(secret_name, safe='')}",
        json_body=compact_payload(
            {
                "projectId": client.default_project_id(project_id),
                "environment": client.default_environment(environment),
                "secretPath": client.default_secret_path(secret_path),
                "secretValue": secret_value,
                "newSecretName": new_secret_name,
                "type": secret_type,
                "secretComment": secret_comment,
            }
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
def delete_secret(
    secret_name: str,
    project_id: str | None = None,
    environment: str | None = None,
    secret_path: str | None = None,
    secret_type: str | None = "shared",
) -> Any:
    """Delete a static secret."""
    client = get_client()
    return client.request(
        "DELETE",
        f"/api/v4/secrets/{quote(secret_name, safe='')}",
        json_body=compact_payload(
            {
                "projectId": client.default_project_id(project_id),
                "environment": client.default_environment(environment),
                "secretPath": client.default_secret_path(secret_path),
                "type": secret_type,
            }
        ),
    )


@mcp.tool(annotations=READ_ONLY)
def render_env_file(
    project_id: str | None = None,
    environment: str | None = None,
    secret_path: str | None = None,
    recursive: bool = False,
    include_imports: bool = False,
) -> str:
    """Render Infisical secrets as .env file content."""
    response = list_secrets(
        project_id=project_id,
        environment=environment,
        secret_path=secret_path,
        recursive=recursive,
        view_secret_value=True,
        expand_secret_references=True,
        include_imports=include_imports,
    )
    return render_env_lines(secret_pairs_from_response(response))


@mcp.tool(annotations=READ_ONLY)
def render_shell_exports(
    project_id: str | None = None,
    environment: str | None = None,
    secret_path: str | None = None,
    recursive: bool = False,
    include_imports: bool = False,
) -> str:
    """Render Infisical secrets as POSIX shell export statements."""
    response = list_secrets(
        project_id=project_id,
        environment=environment,
        secret_path=secret_path,
        recursive=recursive,
        view_secret_value=True,
        expand_secret_references=True,
        include_imports=include_imports,
    )
    return render_shell_export_lines(secret_pairs_from_response(response))


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        mcp.run(
            transport="http",
            host=os.getenv("MCP_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_PORT", "8000")),
        )
        return
    mcp.run()


if __name__ == "__main__":
    main()

