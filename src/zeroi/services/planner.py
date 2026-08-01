from typing import Any

from ..bus import STREAM_PLAN, STREAM_PLAN as STREAM_PLAN_OUT
from ..planner.engine import PlannerEngine
from ..schemas import PlanCompleted, PlanRequest
from ..service import Service

engine = PlannerEngine()


async def handle_plan(service: Service, envelope: dict[str, Any]) -> None:
    etype = envelope.get("type")
    payload = PlanRequest.model_validate(envelope["payload"])

    if etype == "plan.requested":
        plan = await engine.create_plan(payload.session_id, payload.goal, payload.context)
        await service.bus.publish(STREAM_PLAN_OUT, "plan.completed", PlanCompleted(plan=plan))

    elif etype == "plan.replan.requested":
        plan = await engine.replan(
            payload.session_id,
            payload.goal,
            payload.context,
            payload.current_plan,
            payload.failed_task,
            payload.error,
        )
        await service.bus.publish(STREAM_PLAN_OUT, "plan.completed", PlanCompleted(plan=plan, replan=True))


def main() -> None:
    service = Service(name="planner")

    async def handler(envelope: dict[str, Any]) -> None:
        await handle_plan(service, envelope)

    service.handlers = {STREAM_PLAN: handler}
    service.run()


if __name__ == "__main__":
    main()
