import pytest

from zeroi.services.coding_agent import CodingAgent
from zeroi.testing.fakes import FakeService


@pytest.mark.asyncio
async def test_coding_agent_saves_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("zeroi.artifacts.settings.artifact_backend", "local")
    monkeypatch.setattr("zeroi.artifacts.settings.artifact_local_dir", str(tmp_path))

    agent = CodingAgent()
    service = FakeService()

    envelope = {
        "type": "coding.request",
        "payload": {
            "session_id": "sess_plugin",
            "code": "print('hello')",
            "language": "py",
            "filename": "hello.py",
        },
    }

    await agent.handle(service, envelope)

    assert service.bus.published
    stream, event_type, payload = service.bus.published[-1]

    assert stream == "zeroi.coding"
    assert event_type == "coding.completed"
    assert payload["language"] == "py"
    assert payload["artifact"].startswith("file://")
