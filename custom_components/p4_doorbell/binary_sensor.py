"""Radar presence binary sensor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, EVENT_PRESENCE


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([P4PresenceSensor(entry)])


class P4PresenceSensor(BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_has_entity_name = True
    _attr_name = "Presence"

    def __init__(self, entry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_presence"
        self._attr_is_on = False
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_PRESENCE, self._on_presence)
        )

    def _on_presence(self, event) -> None:
        self._attr_is_on = bool(event.data.get("present"))
        self.async_write_ha_state()
