from fastapi import APIRouter, Depends, UploadFile

from ..artifacts import ArtifactStore, artifact_key
from ..security import require_auth
from ..service import Service

store = ArtifactStore()
router = APIRouter()


@router.post("/v1/artifacts/{session_id}/{kind}")
async def upload_artifact(session_id: str, kind: str, file: UploadFile, _=Depends(require_auth)):
    data = await file.read()
    ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "bin"
    key = artifact_key(session_id, kind, ext)
    uri = await store.save_bytes(key, data)
    return {"uri": uri, "key": key}


def main() -> None:
    service = Service(name="artifact_manager", router=router)
    service.run()


if __name__ == "__main__":
    main()
