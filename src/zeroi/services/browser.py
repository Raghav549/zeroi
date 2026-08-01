from typing import Any

from ..browser.agent import BrowserAgent
from ..bus import STREAM_BROWSER, STREAM_TASKS
from ..schemas import StepCompleted, StepExecutionRequest, StepStatus
from ..service import Service

agent = BrowserAgent()


async def handle_browser(service: Service, envelope: dict[str, Any]) -> None:
    if envelope.get("type") != "step.execution.requested":
        return

    req = StepExecutionRequest.model_validate(envelope["payload"])

    try:
        actions = req.payload.get("actions", [])
        result = await agent.execute_flow(req.session_id, actions)

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
    service = Service(name="browser")

    async def handler(envelope: dict[str, Any]) -> None:
        await handle_browser(service, envelope)

    service.handlers = {STREAM_BROWSER: handler}
    service.run()


if __name__ == "__main__":
    main()
