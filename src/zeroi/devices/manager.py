import asyncio
import platform
import shutil
import uuid
from typing import Any

from ..artifacts import ArtifactStore, artifact_key
from ..errors import DeviceError


class DeviceManager:
    def __init__(self) -> None:
        self.artifacts = ArtifactStore()

    async def enumerate_devices(self) -> list[dict[str, Any]]:
        devices = [
            {
                "device_id": "local-desktop",
                "os": platform.system().lower(),
                "type": "desktop",
                "name": platform.node(),
                "displays": [{"display_id": "primary"}],
                "apps": [],
            }
        ]

        adb = shutil.which("adb")
        if adb:
            try:
                proc = await asyncio.create_subprocess_exec(
                    adb,
                    "devices",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                lines = stdout.decode().splitlines()[1:]
                for line in lines:
                    if line.strip() and "device" in line:
                        serial = line.split()[0]
                        devices.append(
                            {
                                "device_id": f"android-{serial}",
                                "os": "android",
                                "type": "mobile",
                                "name": serial,
                                "displays": [{"display_id": "virtual-0"}],
                                "apps": [],
                            }
                        )
            except Exception:
                pass

        return devices

    async def screenshot(self, device_id: str, session_id: str) -> str:
        system = platform.system().lower()

        if device_id.startswith("android-"):
            serial = device_id.replace("android-", "")
            return await self._android_screenshot(serial, session_id)

        if system == "linux":
            return await self._linux_screenshot(session_id)
        if system == "darwin":
            return await self._mac_screenshot(session_id)
        if system == "windows":
            return await self._windows_screenshot(session_id)

        raise DeviceError(f"unsupported device/os: {device_id}/{system}")

    async def _android_screenshot(self, serial: str, session_id: str) -> str:
        adb = shutil.which("adb")
        if not adb:
            raise DeviceError("adb not installed")

        proc = await asyncio.create_subprocess_exec(
            adb,
            "-s",
            serial,
            "exec-out",
            "screencap",
            "-p",
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        key = artifact_key(session_id, "screenshot", "png")
        return await self.artifacts.save_bytes(key, stdout)

    async def _linux_screenshot(self, session_id: str) -> str:
        scrot = shutil.which("scrot")
        if not scrot:
            raise DeviceError("scrot not installed")

        tmp = f"/tmp/zeroi-{uuid.uuid4().hex}.png"
        proc = await asyncio.create_subprocess_exec(scrot, tmp)
        await proc.communicate()

        with open(tmp, "rb") as f:
            data = f.read()

        key = artifact_key(session_id, "screenshot", "png")
        return await self.artifacts.save_bytes(key, data)

    async def _mac_screenshot(self, session_id: str) -> str:
        tmp = f"/tmp/zeroi-{uuid.uuid4().hex}.png"
        proc = await asyncio.create_subprocess_exec("screencapture", "-x", tmp)
        await proc.communicate()

        with open(tmp, "rb") as f:
            data = f.read()

        key = artifact_key(session_id, "screenshot", "png")
        return await self.artifacts.save_bytes(key, data)

    async def _windows_screenshot(self, session_id: str) -> str:
        raise DeviceError("Windows screenshot adapter must be implemented for production deployment")
