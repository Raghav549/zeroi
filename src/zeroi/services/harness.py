from ..bus import STREAM_APPROVALS, STREAM_PLAN, STREAM_REQUESTS, STREAM_TASKS
from ..orchestration.harness import Harness
from ..service import Service


def main() -> None:
    service = Service(name="harness")
    harness = Harness(service.bus)

    service.handlers = {
        STREAM_REQUESTS: harness.handle_requests,
        STREAM_PLAN: harness.handle_plan,
        STREAM_TASKS: harness.handle_task_events,
        STREAM_APPROVALS: harness.handle_approvals,
    }
    service.app.include_router(harness.router)
    service.run()


if __name__ == "__main__":
    main()
