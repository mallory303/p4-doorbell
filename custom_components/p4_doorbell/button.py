"""Test-chime button."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([P4ChimeButton(hass, entry)])


class P4ChimeButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Test chime"
    _attr_icon = "mdi:bell-ring"

    def __init__(self, hass, entry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_chime"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_press(self) -> None:
        api = self._hass.data[DOMAIN][self._entry.entry_id]["api"]
        await api.async_chime()
