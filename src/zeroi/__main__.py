import importlib
import sys

KNOWN_SERVICES = [
    "harness",
    "planner",
    "memory",
    "gui_executor",
    "cli_executor",
    "browser",
    "deepsearch",
    "api_gateway",
    "device_manager",
    "session_manager",
    "artifact_manager",
    "scheduler",
    "notification_processor",
    "event_processor",
    "verification",
    "logging_service",
    "metrics_service",
    "security",
    "coding_agent",
    "research_agent",
]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m zeroi <service-name>")
        print("Services:")
        for name in KNOWN_SERVICES:
            print(f"  {name}")
        raise SystemExit(1)

    service_name = sys.argv[1].replace("-", "_")
    module = importlib.import_module(f"zeroi.services.{service_name}")
    module.main()


if __name__ == "__main__":
    main()
