from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_HOSTS,
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_INTERFACES,
    CONF_TRACKS,
    CONF_TRACK_MAC,
    CONF_TRACK_MACS,
    CONF_TRACK_NAME,
    CONF_TRACK_ICON,
    CONF_TRACK_CONSIDER_HOME,
    CONF_SCAN_INTERVAL,
    CONF_CONSIDER_HOME,
    CONF_MQTT,
    CONF_MQTT_DISCOVERY_PREFIX,
    CONF_MQTT_STATE_PREFIX,
    DEFAULT_SSL,
    DEFAULT_INTERFACES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_DISCOVERY_PREFIX,
    DEFAULT_STATE_PREFIX,
    MQTT_DEVICE_BLOCK,
)
from .luci_api import LuciClient, LuciAuthError

_LOGGER = logging.getLogger(__name__)

HOST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_INTERFACES, default=DEFAULT_INTERFACES): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)

# Track configuration is the VALUE in the mapping; object_id is the KEY.
TRACK_SCHEMA = vol.Schema(
    {
        # Either mac or macs must be provided; we'll validate that in code.
        vol.Optional(CONF_TRACK_MAC): cv.string,
        vol.Optional(CONF_TRACK_MACS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_TRACK_NAME): cv.string,
        vol.Optional(CONF_TRACK_ICON): cv.string,
        vol.Optional(CONF_TRACK_CONSIDER_HOME): vol.Coerce(int),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOSTS): vol.All(cv.ensure_list, [HOST_SCHEMA]),
                vol.Required(CONF_TRACKS): vol.Schema({cv.slug: TRACK_SCHEMA}),
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.Coerce(int),
                vol.Optional(CONF_CONSIDER_HOME, default=DEFAULT_CONSIDER_HOME): vol.Coerce(int),
                vol.Optional(CONF_MQTT, default={}): vol.Schema(
                    {
                        vol.Optional(CONF_MQTT_DISCOVERY_PREFIX, default=DEFAULT_DISCOVERY_PREFIX): cv.string,
                        vol.Optional(CONF_MQTT_STATE_PREFIX, default=DEFAULT_STATE_PREFIX): cv.string,
                    },
                    extra=vol.ALLOW_EXTRA,
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _discovery_topic(discovery_prefix: str, object_id: str) -> str:
    return f"{discovery_prefix}/device_tracker/{object_id}/config"


def _state_topic(state_prefix: str, object_id: str) -> str:
    return f"{state_prefix}/{object_id}/state"


def _normalize_macs(track_conf: dict, object_id: str) -> set[str]:
    macs_list: list[str] = []

    macs = track_conf.get(CONF_TRACK_MACS)
    if macs:
        macs_list.extend(macs)

    mac = track_conf.get(CONF_TRACK_MAC)
    if mac:
        macs_list.append(mac)

    norm = {m.strip().upper() for m in macs_list if m and m.strip()}
    if not norm:
        raise vol.Invalid(f"Track '{object_id}' must define '{CONF_TRACK_MAC}' or '{CONF_TRACK_MACS}'")
    return norm

def _mask_mac(mac: str) -> str:
    """
    Mask MAC for logs. Example:
      FC:31:5D:6C:E9:E5 -> xx:xx:xx:xx:E9:E5
    """
    m = mac.strip().upper()
    parts = m.split(":")
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
    last_state: str | None = None


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    conf = config[DOMAIN]

    scan_interval = int(conf[CONF_SCAN_INTERVAL])
    default_consider_home = int(conf[CONF_CONSIDER_HOME])

    mqtt_conf = conf.get(CONF_MQTT, {})
    discovery_prefix = mqtt_conf.get(CONF_MQTT_DISCOVERY_PREFIX, DEFAULT_DISCOVERY_PREFIX)
    state_prefix = mqtt_conf.get(CONF_MQTT_STATE_PREFIX, DEFAULT_STATE_PREFIX)

    session = async_get_clientsession(hass)

    # Build clients
    clients: list[tuple[LuciClient, list[str]]] = []
    for h in conf[CONF_HOSTS]:
        client = LuciClient(
            host=h[CONF_HOST],
            username=h[CONF_USERNAME],
            password=h[CONF_PASSWORD],
            ssl=h[CONF_SSL],
            session=session,
        )
        ifaces = h.get(CONF_INTERFACES) or []
        clients.append((client, ifaces))

    # Build tracks from dict mapping
    tracks: list[TrackRuntime] = []
    tracks_map: dict = conf[CONF_TRACKS]

    for object_id, t in tracks_map.items():
        name = t.get(CONF_TRACK_NAME) or object_id
        icon = t.get(CONF_TRACK_ICON)
        consider_home = int(t.get(CONF_TRACK_CONSIDER_HOME, default_consider_home))
        macs = _normalize_macs(t, object_id)

        tracks.append(
            TrackRuntime(
                object_id=object_id,
                name=name,
                macs=macs,
                consider_home=consider_home,
                icon=icon,
            )
        )

    # Publish discovery for all tracks (retain)
    for tr in tracks:
        discovery_payload: dict = {
            "name": tr.name,
            "unique_id": f"luci_presence_{tr.object_id}",
            # router-based presence (not GPS)
            "source_type": "router",
            # Allow controlling entity_id at first creation
            "default_entity_id": f"device_tracker.{tr.object_id}",
            "state_topic": _state_topic(state_prefix, tr.object_id),
            "payload_home": "home",
            "payload_not_home": "not_home",
            "device": MQTT_DEVICE_BLOCK,
        }
        if tr.icon:
            discovery_payload["icon"] = tr.icon

        await mqtt.async_publish(
            hass,
            _discovery_topic(discovery_prefix, tr.object_id),
            json.dumps(discovery_payload),
            qos=1,
            retain=True,
        )

    async def _poll_once() -> None:
        # Collect "seen" MACs across all hosts+ifaces (union set)
        seen: set[str] = set()
        for client, ifaces in clients:
            for iface in ifaces:
                try:
                    macs = await client.wifi_assoc_macs(iface)
                except LuciAuthError as exc:
                    _LOGGER.error("LuCI auth error (%s/%s): %s", client.host, iface, exc)
                    continue
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.error("LuCI poll failed (%s/%s): %s", client.host, iface, exc)
                    continue

                seen |= macs

        now = time.time()

        for tr in tracks:
            # If ANY of the MACs is seen, treat as seen
            if tr.macs & seen:
                tr.last_seen = now

            is_home = tr.last_seen is not None and (now - tr.last_seen) <= tr.consider_home
            state = "home" if is_home else "not_home"

            if state != tr.last_state:
                _LOGGER.info(
                    "Presence: %s (object_id=%s macs=%s) => %s (consider_home=%ss last_seen=%s)",
                    tr.name,
                    tr.object_id,
                    sorted(_mask_mac(m) for m in tr.macs),
                    state,
                    tr.consider_home,
                    int(tr.last_seen) if tr.last_seen else None,
                )
                await mqtt.async_publish(
                    hass,
                    _state_topic(state_prefix, tr.object_id),
                    state,
                    qos=0,
                    retain=True,
                )
                tr.last_state = state

    async def _poll_loop() -> None:
        # Initial run
        try:
            await _poll_once()
        except LuciAuthError as exc:
            _LOGGER.error("LuCI auth error (initial poll): %s", exc)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.exception("Unexpected error (initial poll): %s", exc)

        while True:
            await asyncio.sleep(scan_interval)
            try:
                await _poll_once()
            except LuciAuthError as exc:
                _LOGGER.error("LuCI auth error: %s", exc)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.exception("Unexpected error in poll loop: %s", exc)

    # Background task is cancelled automatically on Home Assistant shutdown
    hass.async_create_background_task(_poll_loop(), name=f"{DOMAIN}_poll_loop")

    _LOGGER.info(
        "luci_presence_mqtt started (hosts=%d tracks=%d scan_interval=%ss)",
        len(clients),
        len(tracks),
        scan_interval,
    )
    return True