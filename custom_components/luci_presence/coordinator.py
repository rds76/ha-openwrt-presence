from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic
from typing import Any

from aiohttp import ClientSession, DummyCookieJar
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CONSIDER_HOME,
    CONF_HOST,
    CONF_HOSTS,
    CONF_INTERFACES,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_TRACK_CONSIDER_HOME,
    CONF_TRACK_ICON,
    CONF_TRACK_MAC,
    CONF_TRACK_MACS,
    CONF_TRACK_NAME,
    CONF_TRACKS,
    CONF_USERNAME,
    DOMAIN,
)
from .luci_api import LuciAuthError, LuciClient, LuciCredentialsError, LuciRpcError

_LOGGER = logging.getLogger(__name__)

type LuciPresenceConfigEntry = ConfigEntry[PresenceCoordinator]


def _normalize_macs(track_conf: dict[str, Any], object_id: str) -> set[str]:
    macs_list = list(track_conf.get(CONF_TRACK_MACS) or [])
    if mac := track_conf.get(CONF_TRACK_MAC):
        macs_list.append(mac)
    macs = {mac.strip().upper() for mac in macs_list if mac and mac.strip()}
    if not macs:
        raise vol.Invalid(
            f"Track '{object_id}' must define '{CONF_TRACK_MAC}' or '{CONF_TRACK_MACS}'"
        )
    return macs


def _mask_mac(mac: str) -> str:
    parts = mac.strip().upper().split(":")
    if len(parts) != 6:
        return "<invalid-mac>"
    return "xx:xx:xx:xx:" + ":".join(parts[4:6])


@dataclass
class TrackRuntime:
    object_id: str
    name: str
    macs: set[str]
    consider_home: int
    icon: str | None = None
    last_seen: float | None = None
    last_state: bool | None = None


class PresenceCoordinator(DataUpdateCoordinator[dict[str, bool]]):
    """Poll routers once for all native presence trackers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LuciPresenceConfigEntry,
        conf: dict[str, Any],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=conf[CONF_SCAN_INTERVAL]),
            always_update=False,
        )
        self._host_configs = conf[CONF_HOSTS]
        self._clients: list[tuple[LuciClient, list[str]]] = []
        self._sessions: list[ClientSession] = []
        self._disabled_hosts: set[str] = set()
        self.tracks = [
            TrackRuntime(
                object_id=object_id,
                name=track.get(CONF_TRACK_NAME) or object_id,
                macs=_normalize_macs(track, object_id),
                consider_home=track.get(CONF_TRACK_CONSIDER_HOME, conf[CONF_CONSIDER_HOME]),
                icon=track.get(CONF_TRACK_ICON),
            )
            for object_id, track in conf[CONF_TRACKS].items()
        ]

    def _disable_client(self, client: LuciClient) -> None:
        if client.host in self._disabled_hosts:
            return
        self._disabled_hosts.add(client.host)
        _LOGGER.error(
            "LuCI router %s disabled: authentication failed. Correct its "
            "credentials in configuration.yaml and restart Home Assistant.",
            client.host,
        )

    async def _async_setup(self) -> None:
        for conf in self._host_configs:
            session = async_create_clientsession(
                self.hass, cookie_jar=DummyCookieJar()
            )
            self._sessions.append(session)
            client = LuciClient(
                host=conf[CONF_HOST],
                username=conf[CONF_USERNAME],
                password=conf[CONF_PASSWORD],
                ssl=conf[CONF_SSL],
                session=session,
            )
            try:
                await client.login()
            except LuciCredentialsError:
                self._disable_client(client)
                continue
            except LuciAuthError:
                # The API client logs the failure and retains its retry cooldown.
                pass
            self._clients.append((client, conf[CONF_INTERFACES]))

        if not self._clients:
            raise ConfigEntryError(
                "No LuCI routers are available for polling. Correct the "
                "credentials in configuration.yaml and restart Home Assistant."
            )

    async def _poll_client(self, client: LuciClient, interfaces: list[str]) -> set[str]:
        if client.host in self._disabled_hosts:
            return set()
        seen: set[str] = set()
        for interface in interfaces:
            try:
                seen |= await client.wifi_assoc_macs(interface)
            except LuciCredentialsError:
                self._disable_client(client)
                break
            except LuciAuthError:
                break
            except LuciRpcError as exc:
                _LOGGER.error("LuCI poll failed (%s/%s): %s", client.host, interface, exc)
        return seen

    async def _async_update_data(self) -> dict[str, bool]:
        results = await asyncio.gather(
            *(self._poll_client(client, ifaces) for client, ifaces in self._clients)
        )
        seen: set[str] = set().union(*results)
        now = monotonic()
        states: dict[str, bool] = {}
        for track in self.tracks:
            if track.macs & seen:
                track.last_seen = now
            is_home = (
                track.last_seen is not None
                and now - track.last_seen <= track.consider_home
            )
            states[track.object_id] = is_home
            if is_home != track.last_state:
                _LOGGER.info(
                    "Presence: %s (object_id=%s macs=%s) => %s "
                    "(consider_home=%ss)",
                    track.name,
                    track.object_id,
                    sorted(_mask_mac(mac) for mac in track.macs),
                    "home" if is_home else "not_home",
                    track.consider_home,
                )
                track.last_state = is_home
        return states

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        for session in self._sessions:
            await session.close()
        self._sessions.clear()