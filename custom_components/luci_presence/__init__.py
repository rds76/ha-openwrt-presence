from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

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
    DEFAULT_CONSIDER_HOME,
    DEFAULT_INTERFACES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DOMAIN,
)
from .coordinator import LuciPresenceConfigEntry, PresenceCoordinator

PLATFORMS = [Platform.DEVICE_TRACKER]

HOST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_INTERFACES, default=DEFAULT_INTERFACES): vol.All(
            cv.ensure_list, [cv.string], vol.Length(min=1)
        ),
    }
)

TRACK_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_TRACK_MAC): cv.string,
            vol.Optional(CONF_TRACK_MACS): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_TRACK_NAME): cv.string,
            vol.Optional(CONF_TRACK_ICON): cv.icon,
            vol.Optional(CONF_TRACK_CONSIDER_HOME): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
        }
    ),
    cv.has_at_least_one_key(CONF_TRACK_MAC, CONF_TRACK_MACS),
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOSTS): vol.All(
                    cv.ensure_list, [HOST_SCHEMA], vol.Length(min=1)
                ),
                vol.Required(CONF_TRACKS): vol.All(
                    {cv.slug: TRACK_SCHEMA}, vol.Length(min=1)
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    CONF_CONSIDER_HOME, default=DEFAULT_CONSIDER_HOME
                ): vol.All(vol.Coerce(int), vol.Range(min=0)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Keep YAML as the configuration source and create an imported entry."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = config[DOMAIN]
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: LuciPresenceConfigEntry
) -> bool:
    """Set up native trackers using the configuration read from YAML."""
    if DOMAIN not in hass.data:
        raise ConfigEntryError(
            "Missing luci_presence configuration in configuration.yaml. "
            "Restore the configuration and restart Home Assistant, "
            "or remove this integration."
        )

    coordinator = PresenceCoordinator(hass, entry, hass.data[DOMAIN])
    entry.runtime_data = coordinator
    try:
        await coordinator.async_config_entry_first_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        raise
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LuciPresenceConfigEntry
) -> bool:
    """Unload trackers; the entry's unload hook shuts down the coordinator."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)