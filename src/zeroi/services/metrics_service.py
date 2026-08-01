from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from ..db import SessionLocal
from ..models import SessionRecord, TelemetryRecord
from ..security import require_auth
from ..service import Service

router = APIRouter()


@router.get("/v1/metrics/summary")
async def summary(_=Depends(require_auth)):
    async with SessionLocal() as db:
        sessions = (await db.execute(select(func.count(SessionRecord.id)))).scalar_one()
        telemetry = (await db.execute(select(func.count(TelemetryRecord.id)))).scalar_one()

    return {
        "sessions": sessions,
        "telemetry_events": telemetry,
    }


def main() -> None:
    service = Service(name="metrics_service", router=router)
    service.run()


if __name__ == "__main__":
    main()
