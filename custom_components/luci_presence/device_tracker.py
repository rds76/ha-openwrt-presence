from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LuciPresenceConfigEntry, PresenceCoordinator, TrackRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuciPresenceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        PresenceTracker(entry.runtime_data, track)
        for track in entry.runtime_data.tracks
    )


class PresenceTracker(CoordinatorEntity[PresenceCoordinator], ScannerEntity):
    """Represent one explicitly configured track, possibly with multiple MACs."""

    _attr_entity_registry_enabled_default = True
    _attr_entity_category = None
    _attr_device_info = DeviceInfo()

    def __init__(self, coordinator: PresenceCoordinator, track: TrackRuntime) -> None:
        super().__init__(coordinator)
        self._object_id = track.object_id
        self._attr_name = track.name
        self._attr_icon = track.icon
        self.entity_id = f"device_tracker.{track.object_id}"

    @property
    def unique_id(self) -> str:
        return f"luci_presence_{self._object_id}"

    @property
    def is_connected(self) -> bool:
        return self.coordinator.data[self._object_id]