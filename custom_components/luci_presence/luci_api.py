# Portions adapted from Home Assistant's OpenWrt (LuCI) integration.
# Upstream portions are subject to the Apache License, Version 2.0.
# Modified by rds76 for Wi-Fi association-based presence detection,
# MQTT publishing, and RPC authentication and failure handling.
# See LICENSE, LICENSE-APACHE-2.0 and THIRD_PARTY_NOTICES.txt.

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    LUCIRPC_AUTH_PATH,
    LUCIRPC_SYS_PATH,
    RPC_LOGIN,
    RPC_WIFI_GETIWINFO,
    LOGIN_RETRY_INITIAL,
    LOGIN_RETRY_MAX,
)

_LOGGER = logging.getLogger(__name__)



class LuciRpcError(Exception):
    """RPC communication or response failure."""


class LuciAuthError(LuciRpcError):
    """Authentication failure or login retry cooldown."""


class LuciCredentialsError(LuciAuthError):
    """Router rejected the configured credentials."""


class LuciTokenError(LuciAuthError):
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
        self._next_login = 0.0
        self._retry_delay = LOGIN_RETRY_INITIAL
        self._login_failure_logged = False
        self._credentials_rejected = False

    async def _post_json(self, path: str, payload: dict[str, Any], *, token: str | None = None) -> dict[str, Any]:
        url = f"{self.base}{path}"
        timeout = ClientTimeout(total=self.request_timeout)
        params = {"auth": token} if token is not None else None
        try:
            async with self.session.post(
                url, json=payload, params=params, timeout=timeout
            ) as resp:
                if resp.status in (401, 403):
                    if token is not None:
                        raise LuciTokenError("LuCI RPC rejected the token.")
                    raise LuciCredentialsError("LuCI RPC rejected the login.")
                if resp.status != 200:
                    raise LuciRpcError(f"LuCI RPC HTTP error {resp.status}.")
                data = await resp.json()
        except asyncio.TimeoutError as exc:
            raise LuciRpcError("LuCI RPC request timed out.") from exc
        except (ClientError, ValueError) as exc:
            # aiohttp exception messages can contain the URL and auth token.
            raise LuciRpcError(f"LuCI RPC request failed ({type(exc).__name__}).") from exc

        if not isinstance(data, dict) or "result" not in data:
            raise LuciRpcError("LuCI RPC response is missing a result.")
        if data.get("error") is not None:
            raise LuciRpcError(f"LuCI RPC method {payload['method']} returned an error.")
        if token is not None and data["result"] is None:
            raise LuciTokenError("LuCI RPC returned no authenticated result.")
        return data

    def _defer_login(self, reason: str) -> None:
        self._token = None
        delay = self._retry_delay
        self._next_login = monotonic() + delay
        self._retry_delay = min(delay * 2, LOGIN_RETRY_MAX)
        if not self._login_failure_logged:
            _LOGGER.error("LuCI login unavailable (%s): %s Retrying in %ss; further failures are suppressed until recovery.", self.host, reason, delay)
            self._login_failure_logged = True

    async def login(self, *, rejected_token: str | None = None) -> str:
        """Return a cached token or log in, respecting the router's cooldown."""
        async with self._lock:
            if self._credentials_rejected:
                raise LuciCredentialsError("LuCI credentials were rejected; restart required.")
            # A concurrent request may already have replaced the rejected token.
            if rejected_token is not None and self._token == rejected_token:
                self._token = None
            if self._token is not None:
                return self._token
            if monotonic() < self._next_login:
                raise LuciAuthError("LuCI login retry is deferred.")

            payload = {"method": RPC_LOGIN, "params": [self.username, self.password]}
            _LOGGER.debug("LuCI login attempt (%s).", self.host)
            try:
                data = await self._post_json(LUCIRPC_AUTH_PATH, payload)
                token = data["result"]
                if token is None or token is False or token == "":
                    raise LuciCredentialsError("LuCI RPC rejected the login.")
                if not isinstance(token, str):
                    raise LuciRpcError("LuCI RPC returned an invalid login token.")
            except LuciCredentialsError:
                self._token = None
                self._credentials_rejected = True
                raise
            except LuciRpcError as exc:
                self._defer_login(str(exc))
                raise LuciAuthError("Unable to obtain a LuCI token.") from exc

            self._token = token
            self._next_login = 0.0
            self._retry_delay = LOGIN_RETRY_INITIAL
            if self._login_failure_logged:
                _LOGGER.info("LuCI login recovered (%s).", self.host)
            self._login_failure_logged = False
            return token

    async def _ensure_token(self) -> str:
        return await self.login()

    async def wifi_assoc_macs(self, interface: str) -> set[str]:
        token = await self._ensure_token()
        payload = {"method": RPC_WIFI_GETIWINFO, "params": [interface]}
        _LOGGER.debug("LuCI Wi-Fi query (%s/%s).", self.host, interface)
        try:
            data = await self._post_json(LUCIRPC_SYS_PATH, payload, token=token)
        except LuciTokenError:
            token = await self.login(rejected_token=token)
            try:
                data = await self._post_json(LUCIRPC_SYS_PATH, payload, token=token)
            except LuciTokenError as exc:
                async with self._lock:
                    if self._token == token:
                        self._defer_login("LuCI RPC rejected the refreshed token.")
                raise LuciAuthError("LuCI RPC authentication failed after token refresh.") from exc

        result = data["result"]
        if not isinstance(result, dict):
            raise LuciRpcError("LuCI Wi-Fi result is not an object.")
        assoc = result.get("assoclist") or {}
        if not isinstance(assoc, dict) or any(
            not isinstance(mac, str) for mac in assoc
        ):
            raise LuciRpcError("LuCI Wi-Fi association list is invalid.")
        return {mac.upper() for mac in assoc}
