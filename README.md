# Infisical MCP

FastMCP server for managing a self-hosted Infisical instance from an agent.

Default base URL:

```text
https://infisical-bfi.blueforceinnovations.com
```

## What It Exposes

- Project list/get/create/update/delete tools.
- Environment list/create/update/delete tools.
- Folder list/create/update/delete tools.
- Secret get/list/create/update/delete tools.
- Organization machine identity list/get/create/update/delete tools.
- Project-managed identity list/get/create/update/delete tools.
- Project user and identity membership management tools.
- Project role list/get/create/update/delete tools.
- Organization audit log export tools.
- Secret import list/create/update/delete tools.
- `.env` and shell-export renderers for using Infisical secrets in projects.

The server uses Infisical's documented REST API directly:

- Universal Auth: `POST /api/v1/auth/universal-auth/login`
- Projects: `/api/v1/projects`
- Environments: `/api/v1/projects/{projectId}/environments`
- Organization user memberships: `/api/v2/organizations/{orgId}/memberships`
- Organization identities: `/api/v1/identities`
- Organization identity memberships: `/api/v2/organizations/{orgId}/identity-memberships`
- Project managed identities: `/api/v1/projects/{projectId}/identities`
- Project user memberships: `/api/v1/projects/{projectId}/memberships`
- Project identity memberships: `/api/v1/projects/{projectId}/memberships/identities`
- Project roles: `/api/v1/projects/{projectId}/roles`
- Audit logs: `/api/v1/organization/audit-logs`
- Folders: `/api/v2/folders`
- Static secrets: `/api/v4/secrets`
- Secret imports: `/api/v2/secret-imports`

## Configure

Create a local `.env` from the example:

```bash
cp .env.example .env
```

Use one auth mode.

Token Auth / API-key-like Machine Identity token:

```env
INFISICAL_TOKEN=
```

Universal Auth:

```env
INFISICAL_CLIENT_ID=
INFISICAL_CLIENT_SECRET=
INFISICAL_ORGANIZATION_SLUG=
```

Optional defaults:

```env
INFISICAL_PROJECT_ID=project_uuid
INFISICAL_ENVIRONMENT=dev
INFISICAL_SECRET_PATH=/
```

## Run Locally

```bash
pip install -e .
infisical-mcp
```

By default the server uses stdio, which is the normal transport for local MCP clients.

HTTP is also supported:

```bash
MCP_TRANSPORT=http MCP_HOST=0.0.0.0 MCP_PORT=8000 infisical-mcp
```

## Run With Docker Compose

Build:

```bash
docker compose build
```

Run as a stdio MCP server:

```bash
docker compose run --rm -T infisical-mcp
```

Run as an HTTP MCP server:

```bash
MCP_TRANSPORT=http docker compose up
```

Then connect to:

```text
http://localhost:8000/mcp
```

For a stdio MCP client, configure the command as:

```json
{
  "command": "docker",
  "args": ["compose", "run", "--rm", "-T", "infisical-mcp"]
}
```

## Project Secret Usage

Agents can call `render_env_file` to fetch Infisical secrets as `.env` content:

```env
DATABASE_URL=...
OPENAI_API_KEY=...
```

They can call `render_shell_exports` when a shell session needs exports:

```bash
export DATABASE_URL='...'
export OPENAI_API_KEY='...'
```

The MCP server returns the text. The calling agent decides where, if anywhere, to write it based on the target project permissions.

## Admin Capabilities

The server can manage Infisical administration surfaces when the configured
identity has permission:

- Organization machine identities through `list_identities`, `get_identity`,
  `create_identity`, `update_identity`, and `delete_identity`.
- Organization user memberships through `list_organization_user_memberships`,
  `update_organization_user_membership`, `remove_organization_user_membership`,
  and `remove_organization_user_memberships`.
- Organization identity memberships through
  `list_organization_identity_memberships`.
- Project-managed identities through `list_project_identities`,
  `get_project_identity`, `create_project_identity`,
  `update_project_identity`, and `delete_project_identity`.
- User memberships through `list_project_user_memberships`,
  `get_project_user_by_username`, `invite_project_users`,
  `update_project_user_membership`, and `remove_project_users`.
- Identity memberships through `list_project_identity_memberships`,
  `create_project_identity_membership`, `update_project_identity_membership`,
  and `delete_project_identity_membership`.
- Project roles through `list_project_roles`, `get_project_role_by_slug`,
  `create_project_role`, `update_project_role`, and `delete_project_role`.
- Identity project privileges through
  `create_identity_project_additional_privilege`,
  `get_identity_project_additional_privilege`,
  `update_identity_project_additional_privilege`, and
  `delete_identity_project_additional_privilege`.
- Audit logs through `export_audit_logs`.
- Secret imports through `list_secret_imports`, `create_secret_import`,
  `update_secret_import`, and `delete_secret_import`.

Role assignment tools accept Infisical role objects directly, including
temporary role objects. Project role tools accept Infisical permission rule
objects directly so agents can preserve the full permission grammar.

## Test

```bash
pytest
```
