from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN, DEFAULT_TITLE


class LuciPresenceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Import the YAML configuration without storing credentials in the entry."""

    VERSION = 1

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=DEFAULT_TITLE , data={})

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_abort(reason="yaml_only")