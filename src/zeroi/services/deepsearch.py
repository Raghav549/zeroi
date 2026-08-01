from typing import Any

from ..bus import STREAM_SEARCH, STREAM_TASKS
from ..schemas import StepCompleted, StepExecutionRequest, StepStatus
from ..search.deepsearch import DeepSearchEngine
from ..service import Service

engine = DeepSearchEngine()


async def handle_search(service: Service, envelope: dict[str, Any]) -> None:
    if envelope.get("type") != "step.execution.requested":
        return

    req = StepExecutionRequest.model_validate(envelope["payload"])

    try:
        objective = req.payload.get("objective") or req.context.get("goal", "")
        max_rounds = int(req.payload.get("max_rounds", 2))
        result = await engine.run(objective, max_rounds=max_rounds, context=req.context)

        await service.bus.publish(
            STREAM_TASKS,
            "step.completed",
            StepCompleted(
                session_id=req.session_id,
                task_id=req.task_id,
                step_id=req.step_id,
                status=StepStatus.COMPLETED,
                result=result,
            ),
        )
    except Exception as exc:
        await service.bus.publish(
            STREAM_TASKS,
            "step.failed",
            StepCompleted(
                session_id=req.session_id,
                task_id=req.task_id,
                step_id=req.step_id,
                status=StepStatus.FAILED,
                error=str(exc),
            ),
        )


def main() -> None:
    service = Service(name="deepsearch")

    async def handler(envelope: dict[str, Any]) -> None:
        await handle_search(service, envelope)

    service.handlers = {STREAM_SEARCH: handler}
    service.run()


if __name__ == "__main__":
    main()
