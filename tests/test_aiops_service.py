import pytest

from app.services.aiops_service import AIOpsService


@pytest.mark.asyncio
async def test_aiops_service_maps_supervisor_events():
    class FakeSupervisorService:
        async def execute(self, user_input, session_id):
            yield {
                "kind": "node",
                "node": "planner",
                "state": {"plan": ["step-1", "step-2"]},
            }
            yield {
                "kind": "node",
                "node": "executor",
                "state": {
                    "plan": ["step-2"],
                    "past_steps": [("step-1", "done")],
                },
            }
            yield {
                "kind": "node",
                "node": "replanner",
                "state": {"response": "# report"},
            }
            yield {
                "type": "complete",
                "stage": "complete",
                "message": "任务执行完成",
                "response": "# report",
            }

    service = AIOpsService(supervisor_service=FakeSupervisorService())

    events = [event async for event in service.execute("diagnose", "session-4")]

    assert [event["type"] for event in events] == [
        "plan",
        "step_complete",
        "report",
        "complete",
    ]
    assert events[-1]["response"] == "# report"


@pytest.mark.asyncio
async def test_aiops_service_returns_error_when_supervisor_crashes():
    class FailingSupervisorService:
        async def execute(self, user_input, session_id):
            raise RuntimeError("supervisor crashed")
            yield  # pragma: no cover

    service = AIOpsService(supervisor_service=FailingSupervisorService())

    events = [event async for event in service.execute("diagnose", "session-5")]

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["stage"] == "error"
    assert "supervisor crashed" in events[0]["message"]
