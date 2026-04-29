"""
Replanner node for deciding whether to continue or produce a report.
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


class Response(BaseModel):
    """Structured final response output."""

    response: str = Field(description="Final markdown response for the user.")


class Act(BaseModel):
    """Structured replanner action."""

    action: str = Field(
        description="One of: continue, replan, respond."
    )
    new_steps: List[str] = Field(
        default_factory=list,
        description="Replacement plan when action is replan.",
    )


replanner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent(
                """
                你是运维重规划助手，需要根据已执行步骤决定下一步动作。
                可用工具列表（供你判断计划合理性时参考）：
                {tools_description}

                你的职责是选择：
                - respond：信息已经足够，直接生成最终报告
                - continue：现有计划仍然合理，继续执行
                - replan：现有计划明显不合理，需要替换剩余步骤

                决策优先级：
                1. 能结束就尽快结束，不追求完美
                2. 没有必要时不要 replan
                3. replan 后的新步骤数量不能超过剩余步骤数
                """
            ).strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)

response_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent(
                """
                根据原始任务和已执行步骤的结果，生成全面的最终响应。
                要求：
                - 使用 Markdown
                - 基于工具获得的事实
                - 若步骤失败，必须如实说明
                """
            ).strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)


async def replanner(state: PlanExecuteState) -> Dict[str, Any]:
    """Decide whether to continue, replan, or respond."""
    logger.info("=== Replanner: evaluating next action ===")

    input_text = state.get("input", "")
    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])

    max_steps = 8
    if len(past_steps) >= max_steps:
        logger.warning(
            f"Executed {len(past_steps)} steps, forcing final response generation"
        )
        llm = ChatQwen(
            model=config.rag_model,
            api_key=config.dashscope_api_key,
            temperature=0,
        )
        return await _generate_response(state, llm)

    try:
        all_tools = await get_ops_execution_tools()
        tools_description = format_tools_description(all_tools)
        logger.info(f"Replanner loaded {len(all_tools)} tool(s)")
    except Exception as exc:
        logger.warning(f"Replanner could not load tools: {exc}")
        tools_description = "No tool description available."

    llm = ChatQwen(
        model=config.rag_model,
        api_key=config.dashscope_api_key,
        temperature=0,
    )

    steps_summary = "\n".join(
        f"步骤: {step}\n结果: {result[:300]}..."
        for step, result in past_steps
    )

    if plan:
        replanner_chain = replanner_prompt | llm.with_structured_output(Act)
        try:
            act = await replanner_chain.ainvoke(
                {
                    "messages": [
                        ("user", f"原始任务: {input_text}"),
                        ("user", f"已执行步骤:\n{steps_summary}"),
                        ("user", f"剩余计划: {', '.join(plan)}"),
                        (
                            "user",
                            f"已执行 {len(past_steps)} 个步骤，请优先判断是否足够生成最终报告。",
                        ),
                    ],
                    "tools_description": tools_description,
                }
            )

            if isinstance(act, Act):
                action = act.action
                new_steps = act.new_steps
            else:
                action = act.get("action", "continue")  # type: ignore[assignment]
                new_steps = act.get("new_steps", [])  # type: ignore[assignment]

            logger.info(f"Replanner decision: {action}")

            if action == "respond":
                return await _generate_response(state, llm)

            if action == "replan":
                if len(new_steps) > len(plan):
                    logger.warning(
                        "Replanner proposed too many steps, truncating to remaining plan size"
                    )
                    new_steps = new_steps[: len(plan)]

                if len(past_steps) >= 5:
                    logger.warning(
                        "Replanner exceeded replan threshold, generating final response"
                    )
                    return await _generate_response(state, llm)

                if new_steps:
                    return {"plan": new_steps}

            return {}
        except Exception as exc:
            logger.error(f"Replanner failed: {exc}, continuing with current plan")
            return {}

    logger.info("No remaining plan, generating final response")
    return await _generate_response(state, llm)


async def _generate_response(state: PlanExecuteState, llm: ChatQwen) -> Dict[str, Any]:
    """Generate the final markdown report."""
    logger.info("Generating final AIOps report")

    input_text = state.get("input", "")
    past_steps = state.get("past_steps", [])
    execution_history = "\n\n".join(
        f"### 步骤: {step}\n**结果:**\n{result}" for step, result in past_steps
    )

    response_gen = response_prompt | llm.with_structured_output(Response)
    try:
        response_obj = await response_gen.ainvoke(
            {
                "messages": [
                    ("user", f"原始任务: {input_text}"),
                    ("user", f"执行历史:\n{execution_history}"),
                    ("user", "请基于以上信息生成全面的最终响应。"),
                ]
            }
        )

        if isinstance(response_obj, Response):
            final_response = response_obj.response
        else:
            final_response = response_obj.get("response", "")  # type: ignore[assignment]

        logger.info(f"Generated final response with length {len(final_response)}")
        return {"response": final_response}
    except Exception as exc:
        logger.error(f"Failed to generate final response: {exc}")
        fallback_response = (
            "# 任务执行结果\n\n"
            f"## 原始任务\n{input_text}\n\n"
            f"## 执行的步骤\n{_format_simple_steps(past_steps)}\n\n"
            "## 说明\n由于系统异常，无法生成完整响应。以上是已收集的信息。"
        )
        return {"response": fallback_response}


def _format_simple_steps(past_steps: List[tuple[str, str]]) -> str:
    """Format execution history for the fallback response."""
    if not past_steps:
        return "无"

    formatted = []
    for index, (step, result) in enumerate(past_steps, 1):
        preview = result[:200] + "..." if len(result) > 200 else result
        formatted.append(f"{index}. **{step}**\n   {preview}\n")
    return "\n".join(formatted)
