"""
Knowledge specialist for AIOps supervisor orchestration.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Tuple

from loguru import logger


class KnowledgeSpecialist:
    """Retrieve knowledge-base context for AIOps diagnosis."""

    def __init__(self, retrieve_tool: Any | None = None):
        self.retrieve_tool = retrieve_tool

    def _resolve_tool(self) -> Any:
        if self.retrieve_tool is None:
            from app.tools.knowledge_tool import retrieve_knowledge

            self.retrieve_tool = retrieve_knowledge
        return self.retrieve_tool

    async def run(self, task: str, session_id: str) -> Dict[str, Any]:
        """Retrieve relevant knowledge context for the task."""
        logger.info(f"[session {session_id}] Knowledge specialist started")

        try:
            raw_result = await self._invoke_tool(task)
            context, artifacts = self._normalize_result(raw_result)
            summary = self._build_summary(context=context, artifacts=artifacts)
            logger.info(
                f"[session {session_id}] Knowledge specialist completed, "
                f"context_length={len(context)}, artifacts={len(artifacts)}"
            )
            return {
                "context": context,
                "artifacts": artifacts,
                "summary": summary,
            }
        except Exception as exc:
            logger.warning(
                f"[session {session_id}] Knowledge specialist soft-failed: {exc}"
            )
            return {
                "context": "",
                "artifacts": [],
                "summary": "",
            }

    async def _invoke_tool(self, task: str) -> Any:
        tool = self._resolve_tool()

        if hasattr(tool, "func") and callable(tool.func):
            return await asyncio.to_thread(tool.func, task)

        if hasattr(tool, "ainvoke"):
            return await tool.ainvoke({"query": task})

        if callable(tool):
            return await asyncio.to_thread(tool, task)

        raise TypeError("Unsupported knowledge tool")

    @staticmethod
    def _normalize_result(raw_result: Any) -> Tuple[str, List[Any]]:
        if isinstance(raw_result, tuple) and len(raw_result) == 2:
            context, artifacts = raw_result
            return str(context or ""), list(artifacts or [])

        if isinstance(raw_result, dict):
            context = raw_result.get("context", "")
            artifacts = raw_result.get("artifacts", [])
            return str(context or ""), list(artifacts or [])

        if raw_result is None:
            return "", []

        return str(raw_result), []

    @staticmethod
    def _build_summary(context: str, artifacts: List[Any]) -> str:
        if not context:
            return ""

        if artifacts:
            return (
                f"Retrieved {len(artifacts)} knowledge artifact(s) to support diagnosis."
            )

        preview = context.strip().replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "..."
        return preview
