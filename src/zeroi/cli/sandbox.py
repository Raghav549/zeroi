import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from ..config import settings
from ..errors import SecurityError

log = logging.getLogger(__name__)


class SubprocessSandbox:
    def __init__(self) -> None:
        self.allowlist = set(settings.cli_allowlist_list)
        self.workspace_root = Path(".data/workspaces").absolute()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def _session_workspace(self, session_id: str) -> Path:
        safe = session_id.replace("..", "_")
        path = self.workspace_root / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def run(
        self,
        command: list[str],
        session_id: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> dict[str, Any]:
        if not command:
            raise SecurityError("empty command")

        exe = os.path.basename(command[0])
        if exe not in self.allowlist:
            raise SecurityError(f"executable not allowed: {exe}")

        workdir = self._session_workspace(session_id)
        if cwd:
            requested = (workdir / cwd).resolve()
            if not str(requested).startswith(str(workdir)):
                raise SecurityError("cwd escapes session workspace")
            requested.mkdir(parents=True, exist_ok=True)
            workdir = requested

        safe_env = os.environ.copy()
        if env:
            safe_env.update({k: str(v) for k, v in env.items()})

        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
            env=safe_env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise SecurityError(f"command timed out after {timeout}s")

        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout": stdout.decode(errors="replace")[-100000:],
            "stderr": stderr.decode(errors="replace")[-100000:],
            "cwd": str(workdir),
        }
