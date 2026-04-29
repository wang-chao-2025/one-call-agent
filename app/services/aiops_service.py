"""
Compatibility facade for AIOps diagnosis events.
"""

from typing import Any, AsyncGenerator, Dict

from loguru import logger

from app.agent.aiops.ops_specialist import (
    NODE_EXECUTOR,
    NODE_PLANNER,
    NODE_REPLANNER,
)
from app.agent.aiops.task import build_aiops_task
from app.services.supervisor_aiops_service import supervisor_aiops_service


class AIOpsService:
    """Expose the existing AIOps API while delegating orchestration."""

    def __init__(self, supervisor_service=None):
        self.supervisor_service = supervisor_service or supervisor_aiops_service

    async def execute(
        self,
        user_input: str,
        session_id: str = "default",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute AIOps work and emit backward-compatible events."""
        logger.info(f"[session {session_id}] Start AIOps execution")

        try:
            async for event in self.supervisor_service.execute(user_input, session_id):
                if event.get("kind") == "node":
                    node_name = event.get("node")
                    node_state = event.get("state")

                    if node_name == NODE_PLANNER:
                        yield self._format_planner_event(node_state)
                    elif node_name == NODE_EXECUTOR:
                        yield self._format_executor_event(node_state)
                    elif node_name == NODE_REPLANNER:
                        yield self._format_replanner_event(node_state)
                    continue

                yield event
        except Exception as exc:
            logger.error(
                f"[session {session_id}] AIOps execution failed unexpectedly: {exc}",
                exc_info=True,
            )
            yield {
                "type": "error",
                "stage": "error",
                "message": f"任务执行出错: {exc}",
            }

    async def diagnose(
        self,
        session_id: str = "default",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Diagnose system state using the default AIOps task."""
        async for event in self.execute(build_aiops_task(), session_id):
            if event.get("type") == "complete":
                yield {
                    "type": "complete",
                    "stage": "diagnosis_complete",
                    "message": "诊断流程完成",
                    "diagnosis": {
                        "status": "completed",
                        "report": event.get("response", ""),
                    },
                }
            else:
                yield event

    @staticmethod
    def _format_planner_event(state: Dict[str, Any] | None) -> Dict[str, Any]:
        if not state:
            return {
                "type": "status",
                "stage": "planner",
                "message": "规划节点执行中",
            }

        plan = state.get("plan", [])
        return {
            "type": "plan",
            "stage": "plan_created",
            "message": f"执行计划已制定，共 {len(plan)} 个步骤",
            "plan": plan,
        }

    @staticmethod
    def _format_executor_event(state: Dict[str, Any] | None) -> Dict[str, Any]:
        if not state:
            return {
                "type": "status",
                "stage": "executor",
                "message": "执行节点运行中",
            }

        plan = state.get("plan", [])
        past_steps = state.get("past_steps", [])
        if past_steps:
            last_step, _ = past_steps[-1]
            return {
                "type": "step_complete",
                "stage": "step_executed",
                "message": (
                    f"步骤执行完成 ({len(past_steps)}/{len(past_steps) + len(plan)})"
                ),
                "current_step": last_step,
                "remaining_steps": len(plan),
            }

        return {
            "type": "status",
            "stage": "executor",
            "message": "开始执行步骤",
        }

    @staticmethod
    def _format_replanner_event(state: Dict[str, Any] | None) -> Dict[str, Any]:
        if not state:
            return {
                "type": "status",
                "stage": "replanner",
                "message": "评估节点运行中",
            }

        response = state.get("response", "")
        plan = state.get("plan", [])
        if response:
            return {
                "type": "report",
                "stage": "final_report",
                "message": "最终报告已生成",
                "report": response,
            }

        followup = "继续执行剩余步骤" if plan else "准备生成最终响应"
        return {
            "type": "status",
            "stage": "replanner",
            "message": f"评估完成，{followup}",
            "remaining_steps": len(plan),
        }


aiops_service = AIOpsService()
