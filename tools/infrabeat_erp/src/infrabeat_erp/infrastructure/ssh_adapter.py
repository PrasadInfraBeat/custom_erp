"""Async SSH adapter: paramiko in a thread pool (Sprint 1 Task 4)."""
from __future__ import annotations

import asyncio
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Tuple

import paramiko


class SshAdapter:
    """Wraps paramiko in a ThreadPoolExecutor for asyncio-friendly use.

    paramiko is sync-only. asyncio.run_in_executor moves blocking calls
    off the event loop. One adapter shared across all VM polls.
    """

    def __init__(
        self,
        key_path: Path,
        executor: Optional[ThreadPoolExecutor] = None,
        max_workers: int = 6,
    ) -> None:
        self.key_path = key_path
        self._executor = executor or ThreadPoolExecutor(max_workers=max_workers)
        self._pkey: Optional[paramiko.Ed25519Key] = None

    def _load_pkey(self) -> paramiko.Ed25519Key:
        if self._pkey is None:
            self._pkey = paramiko.Ed25519Key.from_private_key(
                io.StringIO(self.key_path.read_text(encoding="utf-8"))
            )
        return self._pkey

    def _exec_sync(
        self, host: str, user: str, command: str, timeout: int
    ) -> Tuple[int, str, str]:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host,
                username=user,
                pkey=self._load_pkey(),
                timeout=10,
                banner_timeout=10,
                auth_timeout=5,
                allow_agent=False,
                look_for_keys=False,
            )
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            return exit_code, out, err
        finally:
            client.close()

    async def exec(
        self, host: str, user: str, command: str, timeout: int = 10
    ) -> Tuple[int, str, str]:
        """Async wrapper. Returns (exit_code, stdout, stderr)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, self._exec_sync, host, user, command, timeout
        )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
