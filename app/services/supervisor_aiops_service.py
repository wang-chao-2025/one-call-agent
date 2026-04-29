"""
Supervisor service for AIOps specialist orchestration.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, AsyncGenerator, Dict, List, TypedDict

from loguru import logger

from app.agent.aiops.knowledge_specialist import KnowledgeSpecialist
from app.agent.aiops.ops_specialist import OpsSpecialist


class SupervisorAIOpsState(TypedDict):
    """Shared supervisor state for the Phase 1 AIOps MVP."""

    diagnosis_task: str
    session_id: str
    knowledge_context: str
    knowledge_artifacts: List[Any]
    knowledge_summary: str
    plan: List[str]
    past_steps: List[tuple[str, str]]
    response: str


class SupervisorAIOpsService:
    """Deterministically route AIOps work across specialists."""

    def __init__(
        self,
        knowledge_specialist: KnowledgeSpecialist | None = None,
        ops_specialist: OpsSpecialist | None = None,
    ):
        self.knowledge_specialist = knowledge_specialist or KnowledgeSpecialist()
        self.ops_specialist = ops_specialist or OpsSpecialist()
        self.session_states: Dict[str, SupervisorAIOpsState] = {}

    async def execute(
        self,
        diagnosis_task: str,
        session_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute the Phase 1 supervisor flow: Knowledge -> Ops."""
        state: SupervisorAIOpsState = {
            "diagnosis_task": diagnosis_task,
            "session_id": session_id,
            "knowledge_context": "",
            "knowledge_artifacts": [],
            "knowledge_summary": "",
            "plan": [],
            "past_steps": [],
            "response": "",
        }
        self.session_states[session_id] = self._clone_state(state)

        knowledge_result = await self._run_knowledge_specialist(
            diagnosis_task=diagnosis_task,
            session_id=session_id,
        )
        state["knowledge_context"] = knowledge_result.get("context", "")
        state["knowledge_artifacts"] = list(knowledge_result.get("artifacts", []))
        state["knowledge_summary"] = knowledge_result.get("summary", "")
        self.session_states[session_id] = self._clone_state(state)

        try:
            async for event in self.ops_specialist.execute(
                task=diagnosis_task,
                session_id=session_id,
                knowledge_context=state["knowledge_context"],
            ):
                self._merge_ops_event(state, event)
                self.session_states[session_id] = self._clone_state(state)
                yield event
        except Exception as exc:
            logger.error(
                f"[session {session_id}] Supervisor failed while running ops specialist: {exc}",
                exc_info=True,
            )
            error_event = {
                "type": "error",
                "stage": "error",
                "message": f"任务执行出错: {exc}",
            }
            self.session_states[session_id] = self._clone_state(state)
            yield error_event

    async def _run_knowledge_specialist(
        self,
        diagnosis_task: str,
        session_id: str,
    ) -> Dict[str, Any]:
        try:
            return await self.knowledge_specialist.run(diagnosis_task, session_id)
        except Exception as exc:
            logger.warning(
                f"[session {session_id}] Knowledge specialist raised unexpectedly: {exc}"
            )
            return {
                "context": "",
                "artifacts": [],
                "summary": "",
            }

    def get_session_state(self, session_id: str) -> SupervisorAIOpsState | None:
        """Return a copy of the last stored supervisor state."""
        state = self.session_states.get(session_id)
        return self._clone_state(state) if state else None

    @staticmethod
    def _merge_ops_event(
        state: SupervisorAIOpsState,
        event: Dict[str, Any],
    ) -> None:
        if event.get("kind") == "node":
            node_state = event.get("state") or {}
            if "plan" in node_state:
                state["plan"] = list(node_state["plan"])
            if "past_steps" in node_state:
                state["past_steps"].extend(list(node_state["past_steps"]))
            if "response" in node_state:
                state["response"] = str(node_state["response"])
            return

        if event.get("type") == "complete":
            state["response"] = str(event.get("response", ""))

    @staticmethod
    def _clone_state(
        state: SupervisorAIOpsState | None,
    ) -> SupervisorAIOpsState | None:
        return deepcopy(state) if state is not None else None


supervisor_aiops_service = SupervisorAIOpsService()
