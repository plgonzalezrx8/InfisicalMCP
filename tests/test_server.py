from __future__ import annotations


def test_server_module_imports() -> None:
    import infisical_mcp.server as server

    assert server.mcp.name == "Infisical MCP"

