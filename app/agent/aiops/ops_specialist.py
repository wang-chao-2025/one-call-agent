"""
Ops specialist that encapsulates the Plan-Execute-Replan workflow.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict

from langgraph.graph import END, StateGraph
from loguru import logger

from app.agent.aiops.executor import executor
from app.agent.aiops.planner import planner
from app.agent.aiops.replanner import replanner
from app.agent.aiops.state import PlanExecuteState

NODE_PLANNER = "planner"
NODE_EXECUTOR = "executor"
NODE_REPLANNER = "replanner"


class OpsSpecialist:
    """Run the deterministic Plan-Execute-Replan diagnosis loop."""

    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(PlanExecuteState)

        workflow.add_node(NODE_PLANNER, planner)
        workflow.add_node(NODE_EXECUTOR, executor)
        workflow.add_node(NODE_REPLANNER, replanner)

        workflow.set_entry_point(NODE_PLANNER)
        workflow.add_edge(NODE_PLANNER, NODE_EXECUTOR)
        workflow.add_edge(NODE_EXECUTOR, NODE_REPLANNER)

        def should_continue(state: PlanExecuteState) -> str:
            if state.get("response"):
                return END
            if state.get("plan", []):
                return NODE_EXECUTOR
            return END

        workflow.add_conditional_edges(
            NODE_REPLANNER,
            should_continue,
            {
                NODE_EXECUTOR: NODE_EXECUTOR,
                END: END,
            },
        )

        return workflow.compile()

    async def execute(
        self,
        task: str,
        session_id: str,
        knowledge_context: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute the AIOps workflow and stream internal node updates."""
        aggregate_state: PlanExecuteState = {
            "input": task,
            "knowledge_context": knowledge_context,
            "plan": [],
            "past_steps": [],
            "response": "",
        }

        logger.info(f"[session {session_id}] Ops specialist started")

        try:
            async for event in self.graph.astream(
                input=aggregate_state,
                config={"configurable": {"thread_id": session_id}},
                stream_mode="updates",
            ):
                for node_name, node_output in event.items():
                    self._merge_state(aggregate_state, node_output)
                    logger.info(
                        f"[session {session_id}] Ops specialist node finished: {node_name}"
                    )
                    yield {
                        "kind": "node",
                        "node": node_name,
                        "state": node_output,
                    }

            yield {
                "type": "complete",
                "stage": "complete",
                "message": "任务执行完成",
                "response": aggregate_state.get("response", ""),
            }
        except Exception as exc:
            logger.error(
                f"[session {session_id}] Ops specialist failed: {exc}",
                exc_info=True,
            )
            yield {
                "type": "error",
                "stage": "error",
                "message": f"任务执行出错: {exc}",
            }

    @staticmethod
    def _merge_state(
        aggregate_state: PlanExecuteState,
        node_output: Dict[str, Any] | None,
    ) -> None:
        if not node_output:
            return

        for key, value in node_output.items():
            if key == "past_steps":
                aggregate_state.setdefault("past_steps", [])
                aggregate_state["past_steps"] = [
                    *aggregate_state["past_steps"],
                    *list(value),
                ]
            else:
                aggregate_state[key] = value
