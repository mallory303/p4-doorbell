"""Test-ring button: simulates a physical doorbell button press."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([P4TestRingButton(hass, entry)])


class P4TestRingButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Test ring"
    _attr_icon = "mdi:doorbell"

    def __init__(self, hass, entry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_chime"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_press(self) -> None:
        """Full ring pipeline: popup + chime + notifications, exactly like the
        physical button (but without driving the doorbell's own speaker)."""
        manager = self._hass.data[DOMAIN][self._entry.entry_id]["manager"]
        await manager.async_ring(source="simulate")
