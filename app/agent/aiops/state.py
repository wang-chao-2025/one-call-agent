"""
Shared state definitions for the Plan-Execute-Replan workflow.
"""

import operator
from typing import Annotated, List, Tuple, TypedDict


class PlanExecuteState(TypedDict):
    """Plan-Execute-Replan state."""

    input: str
    knowledge_context: str
    plan: List[str]
    past_steps: Annotated[List[Tuple[str, str]], operator.add]
    response: str
