from typing import Any

from ..bus import STREAM_MEMORY, STREAM_TASKS
from ..plugins.base import PluginAgent
from ..plugins.registry import register_plugin
from ..schemas import MemoryKind, MemoryWrite, StepCompleted, StepStatus
from ..search.deepsearch import DeepSearchEngine


@register_plugin
class ResearchAgent(PluginAgent):
    name = "research_agent"
    stream = "zeroi.research"

    def __init__(self) -> None:
        super().__init__()
        self.engine = DeepSearchEngine()

    async def handle(self, service, envelope: dict[str, Any]) -> None:
        if envelope.get("type") not in {"research.request", "step.execution.requested"}:
            return

        outer = envelope.get("payload", {})
        inner = outer.get("payload", outer)

        session_id = outer.get("session_id") or inner.get("session_id", "global")
        task_id = outer.get("task_id")
        step_id = outer.get("step_id")

        objective = inner.get("objective") or inner.get("goal") or ""
        max_rounds = int(inner.get("max_rounds", 2))

        result = await self.engine.run(objective, max_rounds=max_rounds, context=inner)

        await service.bus.publish(
            STREAM_MEMORY,
            "memory.write",
            MemoryWrite(
                kind=MemoryKind.SEMANTIC,
                content=f"Research result for: {objective}\n\n{result.get('answer', '')}",
                tags=["research", "deepsearch"],
                metadata={"objective": objective, "session_id": session_id},
            ),
        )

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
                ),
            )
        else:
            await service.bus.publish(self.stream, "research.completed", result)


def main() -> None:
    agent = ResearchAgent()
    service = agent.build_service()
    service.run()


if __name__ == "__main__":
    main()
