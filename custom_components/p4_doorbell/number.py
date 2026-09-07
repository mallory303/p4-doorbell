"""Speaker volume number entity (maps to GET/POST /api/volume on the P4)."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([P4VolumeNumber(hass, entry)])


class P4VolumeNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Speaker volume"
    _attr_icon = "mdi:volume-high"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"

    def __init__(self, hass, entry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_volume"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def _api(self):
        return self._hass.data[DOMAIN][self._entry.entry_id]["api"]

    async def async_update(self) -> None:
        try:
            self._attr_native_value = await self._api.async_get_volume()
            self._attr_available = True
        except Exception:  # noqa: BLE001
            self._attr_available = False

    async def async_set_native_value(self, value: float) -> None:
        await self._api.async_set_volume(int(value))
        self._attr_native_value = value
        self.async_write_ha_state()
