#!/usr/bin/env python3
"""Thin wrapper around the public @ha7ch/job-pro CLI (no login, no BOSS/Zhilian)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any, Optional

DEFAULT_MIN_INTERVAL = 1.05


class JobProError(RuntimeError):
    pass


class JobProClient:
    def __init__(
        self,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        timeout: float = 90.0,
        npx_bin: Optional[str] = None,
    ) -> None:
        self.min_interval = max(1.0, float(min_interval))
        self.timeout = timeout
        self.npx = npx_bin or shutil.which("npx") or "npx"
        self._last_call = 0.0
        self.package = os.environ.get("JOB_PRO_PACKAGE", "@ha7ch/job-pro@latest")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _run(self, args: list[str]) -> dict[str, Any]:
        self._throttle()
        cmd = [self.npx, "--yes", self.package, *args, "--compact"]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, "PATH": os.environ.get("PATH", "")},
            )
        except subprocess.TimeoutExpired as exc:
            self._last_call = time.monotonic()
            raise JobProError(f"timeout after {self.timeout}s: {' '.join(args)}") from exc
        self._last_call = time.monotonic()
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if not stdout:
            raise JobProError(f"empty stdout (exit={proc.returncode}): {' '.join(args)}; stderr={stderr[:400]}")
        # job-pro may print npm notices before JSON; take last JSON object line.
        payload = None
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            if line.startswith("{") or line.startswith("["):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        if payload is None:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError as exc:
                raise JobProError(
                    f"non-JSON output (exit={proc.returncode}): {stdout[:300]} | stderr={stderr[:200]}"
                ) from exc
        if isinstance(payload, dict) and payload.get("ok") is False:
            raise JobProError(payload.get("message") or str(payload))
        return payload  # type: ignore[return-value]

    def list_companies(self) -> list[dict[str, Any]]:
        data = self._run(["list"])
        if isinstance(data, list):
            return data
        return data.get("companies") or data.get("items") or []

    def search(
        self,
        company: str,
        keyword: str = "",
        *,
        scope: str = "campus",
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        args = [company, "search", keyword if keyword is not None else "", "--scope", scope, "--page-size", str(page_size)]
        if page and page > 1:
            args.extend(["--page", str(page)])
        return self._run(args)

    def detail(self, company: str, post_id: str) -> dict[str, Any]:
        return self._run([company, "detail", str(post_id)])
