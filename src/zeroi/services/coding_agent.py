from typing import Any

from ..artifacts import ArtifactStore, artifact_key
from ..bus import STREAM_TASKS
from ..plugins.base import PluginAgent
from ..plugins.registry import register_plugin
from ..schemas import StepCompleted, StepStatus


@register_plugin
class CodingAgent(PluginAgent):
    name = "coding_agent"
    stream = "zeroi.coding"

    def __init__(self) -> None:
        super().__init__()
        self.store = ArtifactStore()

    async def handle(self, service, envelope: dict[str, Any]) -> None:
        if envelope.get("type") not in {"coding.request", "step.execution.requested"}:
            return

        outer = envelope.get("payload", {})
        inner = outer.get("payload", outer)

        session_id = outer.get("session_id") or inner.get("session_id", "global")
        task_id = outer.get("task_id")
        step_id = outer.get("step_id")

        code = inner.get("code", "")
        language = inner.get("language", "py")
        filename = inner.get("filename", f"main.{language}")

        ext = filename.split(".")[-1] if "." in filename else "txt"
        key = artifact_key(session_id, "code", ext)
        uri = await self.store.save_text(key, code)

        result = {
            "language": language,
            "filename": filename,
            "artifact": uri,
            "bytes": len(code.encode()),
        }

        if task_id and step_id:
            await service.bus.publish(
                STREAM_TASKS,
                "step.completed",
                StepCompleted(
                    session_id=session_id,
                    task_id=task_id,
                    step_id=step_id,
                    status=StepStatus.COMPLETED,
                    result=result,
                    artifacts=[uri],
                ),
            )
        else:
            await service.bus.publish(self.stream, "coding.completed", result)


def main() -> None:
    agent = CodingAgent()
    service = agent.build_service()
    service.run()


if __name__ == "__main__":
    main()
