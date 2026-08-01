from typing import Any

from ..bus import STREAM_GUI, STREAM_TASKS
from ..gui.qwen_adapter import QwenUIAgentAdapter
from ..schemas import GUIBatch, Observation, StepCompleted, StepExecutionRequest, StepStatus
from ..service import Service

adapter = QwenUIAgentAdapter()


async def handle_gui(service: Service, envelope: dict[str, Any]) -> None:
    if envelope.get("type") != "step.execution.requested":
        return

    req = StepExecutionRequest.model_validate(envelope["payload"])

    try:
        if req.kind == "GUI_OBJECTIVE":
            result = await adapter.execute_goal(
                req.payload.get("objective", ""),
                req.payload.get("device"),
                req.context,
            )
        elif req.kind == "GUI_BATCH":
            batch = GUIBatch.model_validate(req.payload.get("batch", {}))
            result = await adapter.execute_batch(batch, req.context)
        else:
            raise ValueError(f"unsupported GUI kind: {req.kind}")

        observation = Observation(
            screenshot_uri=result.get("screenshot_uri"),
            ui_tree=result.get("ui_tree"),
            ocr=result.get("ocr"),
        )

        await service.bus.publish(
            STREAM_TASKS,
            "step.completed",
            StepCompleted(
                session_id=req.session_id,
                task_id=req.task_id,
                step_id=req.step_id,
                status=StepStatus.COMPLETED,
                result=result,
                artifacts=result.get("artifacts", []),
                observations=[observation],
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
    service = Service(name="gui_executor")

    async def handler(envelope: dict[str, Any]) -> None:
        await handle_gui(service, envelope)

    service.handlers = {STREAM_GUI: handler}
    service.run()


if __name__ == "__main__":
    main()
