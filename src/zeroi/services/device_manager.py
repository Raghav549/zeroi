from fastapi import APIRouter, Depends

from ..devices.manager import DeviceManager
from ..security import require_auth
from ..service import Service

manager = DeviceManager()
router = APIRouter()


@router.get("/v1/devices")
async def list_devices(_=Depends(require_auth)):
    return await manager.enumerate_devices()


@router.post("/v1/devices/{device_id}/screenshot")
async def take_screenshot(device_id: str, session_id: str = "global", _=Depends(require_auth)):
    uri = await manager.screenshot(device_id, session_id)
    return {"uri": uri}


def main() -> None:
    service = Service(name="device_manager", router=router)
    service.run()


if __name__ == "__main__":
    main()
