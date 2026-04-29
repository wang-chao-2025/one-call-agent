"""
Planner node for the Plan-Execute-Replan workflow.
"""

from textwrap import dedent
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_qwq import ChatQwen
from loguru import logger
from pydantic import BaseModel, Field

from app.config import config
from .state import PlanExecuteState
from .tooling import get_ops_execution_tools
from .utils import format_tools_description


class Plan(BaseModel):
    """Structured planner output."""

    steps: List[str] = Field(
        description=(
            "A short ordered list of concrete steps required to complete the task."
        )
    )


planner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent(
                """
                你是一个专业的运维规划助手，需要把复杂任务拆解为可执行步骤。
                可用工具列表（供你规划时参考）：
                {tools_description}

                你的职责是制定计划，真正的工具调用由执行节点负责。
                {experience_context}

                计划要求：
                - 步骤按顺序组织
                - 每一步都应具体、可操作
                - 优先引用已有运维经验和最佳实践
                - 如果任务涉及日志或监控，请明确指出要查询的对象或范围
                """
            ).strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)


async def planner(state: PlanExecuteState) -> Dict[str, Any]:
    """Generate an execution plan from the task and supervisor context."""
    logger.info("=== Planner: generating execution plan ===")

    input_text = state.get("input", "")
    experience_docs = (state.get("knowledge_context", "") or "").strip()

    try:
        all_tools = await get_ops_execution_tools()
        logger.info(f"Planner loaded {len(all_tools)} tool(s)")
        tools_description = format_tools_description(all_tools)

        if experience_docs:
            experience_context = dedent(
                f"""
                ## Relevant Knowledge

                The supervisor retrieved the following knowledge context.
                Use it when deciding the diagnosis steps:

                {experience_docs}

                ---
                """
            ).strip()
        else:
            experience_context = ""

        llm = ChatQwen(
            model=config.rag_model,
            api_key=config.dashscope_api_key,
            temperature=0,
        )
        planner_chain = planner_prompt | llm.with_structured_output(Plan)

        plan_result = await planner_chain.ainvoke(
            {
                "messages": [("user", input_text)],
                "tools_description": tools_description,
                "experience_context": experience_context,
            }
        )

        if isinstance(plan_result, Plan):
            plan_steps = plan_result.steps
        else:
            plan_steps = plan_result.get("steps", [])  # type: ignore[assignment]

        logger.info(f"Planner generated {len(plan_steps)} step(s)")
        return {"plan": plan_steps}
    except Exception as exc:
        logger.error(f"Planner failed: {exc}", exc_info=True)
        return {
            "plan": [
                "收集当前告警和监控信息",
                "检查相关日志和服务状态",
                "总结证据并生成诊断报告",
            ]
        }
