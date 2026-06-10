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
- `.env` and shell-export renderers for using Infisical secrets in projects.

The server uses Infisical's documented REST API directly:

- Universal Auth: `POST /api/v1/auth/universal-auth/login`
- Projects: `/api/v1/projects`
- Environments: `/api/v1/projects/{projectId}/environments`
- Folders: `/api/v2/folders`
- Static secrets: `/api/v4/secrets`

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

## Test

```bash
pytest
```
