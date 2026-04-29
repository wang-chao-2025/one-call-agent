import pytest

from app.services.supervisor_aiops_service import SupervisorAIOpsService


@pytest.mark.asyncio
async def test_supervisor_runs_knowledge_before_ops():
    calls = []

    class FakeKnowledgeSpecialist:
        async def run(self, task, session_id):
            calls.append(("knowledge", task, session_id))
            return {
                "context": "knowledge context",
                "artifacts": ["doc-1"],
                "summary": "summary",
            }

    class FakeOpsSpecialist:
        async def execute(self, task, session_id, knowledge_context):
            calls.append(("ops", task, session_id, knowledge_context))
            yield {
                "type": "complete",
                "stage": "complete",
                "message": "done",
                "response": "# report",
            }

    service = SupervisorAIOpsService(
        knowledge_specialist=FakeKnowledgeSpecialist(),
        ops_specialist=FakeOpsSpecialist(),
    )

    events = [event async for event in service.execute("diagnose", "session-1")]

    assert calls == [
        ("knowledge", "diagnose", "session-1"),
        ("ops", "diagnose", "session-1", "knowledge context"),
    ]
    assert events[-1]["type"] == "complete"
    assert service.get_session_state("session-1")["response"] == "# report"


@pytest.mark.asyncio
async def test_supervisor_soft_fails_knowledge_specialist():
    calls = []

    class FailingKnowledgeSpecialist:
        async def run(self, task, session_id):
            calls.append("knowledge")
            raise RuntimeError("knowledge unavailable")

    class FakeOpsSpecialist:
        async def execute(self, task, session_id, knowledge_context):
            calls.append(("ops", knowledge_context))
            yield {
                "type": "complete",
                "stage": "complete",
                "message": "done",
                "response": "# report",
            }

    service = SupervisorAIOpsService(
        knowledge_specialist=FailingKnowledgeSpecialist(),
        ops_specialist=FakeOpsSpecialist(),
    )

    events = [event async for event in service.execute("diagnose", "session-2")]

    assert calls == ["knowledge", ("ops", "")]
    assert events[-1]["type"] == "complete"
    assert service.get_session_state("session-2")["knowledge_context"] == ""


@pytest.mark.asyncio
async def test_supervisor_returns_error_when_ops_specialist_fails():
    class FakeKnowledgeSpecialist:
        async def run(self, task, session_id):
            return {
                "context": "knowledge context",
                "artifacts": [],
                "summary": "summary",
            }

    class FailingOpsSpecialist:
        async def execute(self, task, session_id, knowledge_context):
            raise RuntimeError("ops failed")
            yield  # pragma: no cover

    service = SupervisorAIOpsService(
        knowledge_specialist=FakeKnowledgeSpecialist(),
        ops_specialist=FailingOpsSpecialist(),
    )

    events = [event async for event in service.execute("diagnose", "session-3")]

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["stage"] == "error"
    assert "ops failed" in events[0]["message"]
