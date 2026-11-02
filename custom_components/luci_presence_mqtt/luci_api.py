from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .const import (
    LUCIRPC_AUTH_PATH,
    LUCIRPC_SYS_PATH,
    RPC_LOGIN,
    RPC_WIFI_GETIWINFO,
)

_LOGGER = logging.getLogger(__name__)


class LuciAuthError(Exception):
    """Authentication failure."""


class LuciTokenError(Exception):
    """Invalid/expired token."""


@dataclass
class LuciClient:
    host: str
    username: str
    password: str
    ssl: bool
    session: ClientSession
    request_timeout: int = 5

    def __post_init__(self) -> None:
        scheme = "https" if self.ssl else "http"
        self.base = f"{scheme}://{self.host}"
        self._token: str | None = None
        self._lock = asyncio.Lock()

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        url = f"{self.base}{path}"
        timeout = ClientTimeout(total=self.request_timeout)
        try:
            async with self.session.post(url, json=payload, timeout=timeout) as resp:
                if resp.status == 401:
                    raise LuciAuthError("LuCI RPC authentication failed (401).")
                if resp.status == 403:
                    raise LuciTokenError("LuCI RPC invalid token (403).")
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error("LuCI RPC error %s: %s", resp.status, text)
                    return None
                return await resp.json()
        except asyncio.TimeoutError:
            _LOGGER.error("LuCI RPC timeout talking to %s", url)
            return None

    async def login(self) -> str | None:
        payload = {"method": RPC_LOGIN, "params": [self.username, self.password]}
        data = await self._post_json(LUCIRPC_AUTH_PATH, payload)
        if not data or "result" not in data:
            return None
        token = data["result"]
        if not token:
            return None
        self._token = token
        return token

    async def _ensure_token(self) -> str | None:
        async with self._lock:
            if self._token is not None:
                return self._token
            return await self.login()

    async def wifi_assoc_macs(self, interface: str) -> set[str]:
        token = await self._ensure_token()
        if not token:
            raise LuciAuthError("Failed to obtain LuCI token")

        payload = {"method": RPC_WIFI_GETIWINFO, "params": [interface]}
        try:
            data = await self._post_json(LUCIRPC_SYS_PATH, payload)
        except LuciTokenError:
            self._token = None
            token = await self.login()
            if not token:
                raise
            data = await self._post_json(LUCIRPC_SYS_PATH, payload)

        if not data or "result" not in data or not data["result"]:
            return set()

        result = data["result"]
        assoc = result.get("assoclist") or {}
        return {mac.upper() for mac in assoc.keys()}