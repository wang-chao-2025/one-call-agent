import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.aiops import router
from app.services.aiops_service import aiops_service


def _parse_sse_messages(raw_text: str):
    messages = []
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            messages.append(json.loads(line[6:]))
    return messages


def test_aiops_api_sse_contract(monkeypatch):
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

    monkeypatch.setattr(aiops_service, "supervisor_service", FakeSupervisorService())

    app = FastAPI()
    app.include_router(router, prefix="/api")

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/aiops",
            json={"session_id": "session-6"},
        ) as response:
            payload = "".join(response.iter_text())

    messages = _parse_sse_messages(payload)

    assert [message["type"] for message in messages] == [
        "plan",
        "step_complete",
        "report",
        "complete",
    ]
    assert messages[-1]["stage"] == "diagnosis_complete"
    assert messages[-1]["diagnosis"]["report"] == "# report"
