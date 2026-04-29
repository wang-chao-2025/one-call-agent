"""
Executor node for running a single plan step.
"""

from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_qwq import ChatQwen
from langgraph.prebuilt import ToolNode
from loguru import logger

from app.config import config
from .state import PlanExecuteState
from .tooling import get_ops_execution_tools


async def executor(state: PlanExecuteState) -> Dict[str, Any]:
    """Execute the next step in the plan."""
    logger.info("=== Executor: running current step ===")

    plan = state.get("plan", [])
    if not plan:
        logger.info("Executor skipped because plan is empty")
        return {}

    task = plan[0]
    logger.info(f"Current task: {task}")

    try:
        all_tools = await get_ops_execution_tools()
        logger.info(f"Executor loaded {len(all_tools)} tool(s)")

        llm = ChatQwen(
            model=config.rag_model,
            api_key=config.dashscope_api_key,
            temperature=0,
        )
        llm_with_tools = llm.bind_tools(all_tools)
        tool_node = ToolNode(all_tools)

        messages = [
            SystemMessage(
                content=(
                    "你是运维步骤执行助手，只需要完成当前步骤。"
                    "优先使用日志、监控和时间相关工具获取事实，不要编造信息。"
                    "如果工具调用失败，请明确说明失败原因。"
                )
            ),
            HumanMessage(content=f"请执行以下任务步骤：{task}"),
        ]

        llm_response = await llm_with_tools.ainvoke(messages)
        logger.info(f"Executor initial response type: {type(llm_response)}")

        if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            logger.info(
                f"Executor detected {len(llm_response.tool_calls)} tool call(s)"
            )
            messages.append(llm_response)
            tool_messages = await tool_node.ainvoke({"messages": messages})
            messages.extend(tool_messages["messages"])
            final_response = await llm_with_tools.ainvoke(messages)
            result = (
                final_response.content
                if hasattr(final_response, "content")
                else str(final_response)
            )
        else:
            result = (
                llm_response.content
                if hasattr(llm_response, "content")
                else str(llm_response)
            )

        logger.info(f"Executor completed step with result length {len(result)}")
        return {
            "plan": plan[1:],
            "past_steps": [(task, result)],
        }
    except Exception as exc:
        logger.error(f"Executor failed: {exc}", exc_info=True)
        return {
            "plan": plan[1:],
            "past_steps": [(task, f"执行失败: {exc}")],
        }
