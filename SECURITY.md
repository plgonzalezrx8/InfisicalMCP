# Security

This MCP server can retrieve and render Infisical secrets. Treat its runtime
environment as sensitive.

## Credential Handling

- Do not commit `.env`, access tokens, client secrets, rendered `.env` files, or
  shell export output.
- Use `.env.example` as the only committed environment template.
- Prefer Infisical Machine Identity credentials scoped to the minimum projects
  and environments the agent needs.
- Rotate credentials immediately if a local `.env` or rendered secret file is
  accidentally committed or shared.

## Public Repository Checks

Before publishing changes, run:

```bash
python -m pytest
python -m compileall src tests
rg -n "(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|INFISICAL_(TOKEN|API_KEY|CLIENT_SECRET)=.+|clientSecret[[:space:]]*[:=][[:space:]]*['\"]?[A-Za-z0-9_-]{12,})" -S .
```

The secret scan should return no matches.

