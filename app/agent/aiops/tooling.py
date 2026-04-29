"""
Shared tool loading for AIOps specialists.
"""

from typing import Any, Dict, List

from app.agent.mcp_client import get_mcp_client_with_retry
from app.config import config
from app.tools.time_tool import get_current_time

OPS_SERVER_NAMES = ("cls", "monitor")


def get_ops_server_configs() -> Dict[str, Dict[str, Any]]:
    """Return the MCP server subset used by the ops specialist."""
    return {
        name: config.mcp_servers[name]
        for name in OPS_SERVER_NAMES
        if name in config.mcp_servers
    }


async def get_ops_mcp_tools(client_factory=None) -> List[Any]:
    """Load MCP tools limited to the AIOps execution servers."""
    factory = client_factory or get_mcp_client_with_retry
    client = await factory(servers=get_ops_server_configs(), force_new=True)
    return await client.get_tools()


async def get_ops_execution_tools(client_factory=None) -> List[Any]:
    """Load the tools exposed to the ops specialist executor."""
    return [get_current_time, *await get_ops_mcp_tools(client_factory)]


async def get_ops_execution_tool_names(client_factory=None) -> List[str]:
    """Return tool names for diagnostics and tests."""
    tools = await get_ops_execution_tools(client_factory)
    return [tool.name if hasattr(tool, "name") else str(tool) for tool in tools]
