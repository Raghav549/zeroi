import json
import os
import uuid
from pathlib import Path
from typing import Any

from .config import settings
from .errors import ArtifactError


class ArtifactStore:
    def __init__(self) -> None:
        self.backend = settings.artifact_backend
        self.local_dir = Path(settings.artifact_local_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)

    def _local_path(self, key: str) -> Path:
        safe = key.replace("..", "_")
        path = self.local_dir / safe
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def save_bytes(self, key: str, data: bytes) -> str:
        if self.backend == "local":
            path = self._local_path(key)
            path.write_bytes(data)
            return f"file://{path.absolute()}"

        if self.backend == "s3":
            return self._save_s3(key, data)

        raise ArtifactError(f"unsupported artifact backend: {self.backend}")

    async def save_json(self, key: str, obj: Any) -> str:
        return await self.save_bytes(key, json.dumps(obj, indent=2, default=str).encode())

    async def save_text(self, key: str, text: str) -> str:
        return await self.save_bytes(key, text.encode())

    async def load_bytes(self, key: str) -> bytes:
        if self.backend == "local":
            path = self._local_path(key)
            if not path.exists():
                raise ArtifactError(f"artifact not found: {key}")
            return path.read_bytes()

        raise ArtifactError("load_bytes only implemented for local backend in scaffold")

    def _save_s3(self, key: str, data: bytes) -> str:
        try:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint or None,
                aws_access_key_id=settings.aws_access_key_id or None,
                aws_secret_access_key=settings.aws_secret_access_key or None,
            )
            client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data)
            return f"s3://{settings.s3_bucket}/{key}"
        except Exception as exc:
            raise ArtifactError(f"s3 upload failed: {exc}") from exc


def artifact_key(session_id: str, kind: str, ext: str = "json") -> str:
    return f"{session_id}/{kind}/{uuid.uuid4().hex}.{ext}"


artifacts = ArtifactStore()
