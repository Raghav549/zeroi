import pytest

from zeroi.artifacts import ArtifactStore


@pytest.mark.asyncio
async def test_local_artifact_save_load(tmp_path, monkeypatch):
    monkeypatch.setattr("zeroi.artifacts.settings.artifact_backend", "local")
    monkeypatch.setattr("zeroi.artifacts.settings.artifact_local_dir", str(tmp_path))

    store = ArtifactStore()

    uri = await store.save_text("test/file.txt", "hello zeroi")
    assert uri.startswith("file://")

    data = await store.load_bytes("test/file.txt")
    assert data == b"hello zeroi"


@pytest.mark.asyncio
async def test_local_json_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("zeroi.artifacts.settings.artifact_backend", "local")
    monkeypatch.setattr("zeroi.artifacts.settings.artifact_local_dir", str(tmp_path))

    store = ArtifactStore()

    uri = await store.save_json("test/data.json", {"ok": True})
    assert uri.startswith("file://")

    data = await store.load_bytes("test/data.json")
    assert b'"ok": true' in data
