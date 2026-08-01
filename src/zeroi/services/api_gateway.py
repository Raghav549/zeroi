from typing import Any

from ..api_gateway.tools import execute_api
from ..bus import STREAM_API, STREAM_TASKS
from ..schemas import StepCompleted, StepExecutionRequest, StepStatus
from ..service import Service


async def handle_api(service: Service, envelope: dict[str, Any]) -> None:
    if envelope.get("type") != "step.execution.requested":
        return

    req = StepExecutionRequest.model_validate(envelope["payload"])

    try:
        result = await execute_api(req.payload)
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
    service = Service(name="api_gateway")

    async def handler(envelope: dict[str, Any]) -> None:
        await handle_api(service, envelope)

    service.handlers = {STREAM_API: handler}
    service.run()


if __name__ == "__main__":
    main()
