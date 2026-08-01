from typing import Any

from ..bus import STREAM_CLI, STREAM_TASKS
from ..cli.sandbox import SubprocessSandbox
from ..schemas import StepCompleted, StepExecutionRequest, StepStatus
from ..service import Service

sandbox = SubprocessSandbox()


async def handle_cli(service: Service, envelope: dict[str, Any]) -> None:
    if envelope.get("type") != "step.execution.requested":
        return

    req = StepExecutionRequest.model_validate(envelope["payload"])

    try:
        command = req.payload.get("command")
        if not command:
            raise ValueError("CLI payload missing command")

        result = await sandbox.run(
            command=command,
            session_id=req.session_id,
            cwd=req.payload.get("cwd"),
            env=req.payload.get("env"),
            timeout=int(req.payload.get("timeout", 60)),
        )

        if result.get("returncode") != 0:
            raise RuntimeError(result.get("stderr") or "CLI command failed")

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
    service = Service(name="cli_executor")

    async def handler(envelope: dict[str, Any]) -> None:
        await handle_cli(service, envelope)

    service.handlers = {STREAM_CLI: handler}
    service.run()


if __name__ == "__main__":
    main()
