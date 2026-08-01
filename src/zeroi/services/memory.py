from ..bus import STREAM_MEMORY
from ..memory.service import MemoryService
from ..service import Service


def main() -> None:
    memory = MemoryService()
    service = Service(
        name="memory",
        handlers={STREAM_MEMORY: memory.handle_memory_events},
        router=memory.router,
    )
    service.run()


if __name__ == "__main__":
    main()
