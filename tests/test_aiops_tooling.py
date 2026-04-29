from types import SimpleNamespace

import pytest

from app.agent.aiops.tooling import get_ops_execution_tool_names


@pytest.mark.asyncio
async def test_ops_execution_tools_exclude_knowledge(monkeypatch):
    class FakeClient:
        async def get_tools(self):
            return [
                SimpleNamespace(name="search_log"),
                SimpleNamespace(name="query_cpu_metrics"),
            ]

    async def fake_get_mcp_client_with_retry(*, servers=None, force_new=False, **kwargs):
        assert set(servers) == {"cls", "monitor"}
        assert force_new is True
        return FakeClient()

    monkeypatch.setattr(
        "app.agent.aiops.tooling.get_mcp_client_with_retry",
        fake_get_mcp_client_with_retry,
    )

    tool_names = await get_ops_execution_tool_names()

    assert "get_current_time" in tool_names
    assert "retrieve_knowledge" not in tool_names
