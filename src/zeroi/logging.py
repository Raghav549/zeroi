import logging
import sys

from pythonjsonlogger import jsonlogger

from .config import settings


def setup_logging(service_name: str) -> None:
    logger = logging.getLogger()
    logger.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        defaults={"service": service_name},
    )
    handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(handler)
