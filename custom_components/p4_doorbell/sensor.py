"""Call state sensor (drives the popup talkback page and automations)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from .call_manager import CallManager
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data is None:
        return
    async_add_entities([P4DoorbellCallStateSensor(entry, data["manager"])])


class P4DoorbellCallStateSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Call state"
    _attr_icon = "mdi:phone"
    _attr_should_poll = False

    def __init__(self, entry, manager: CallManager) -> None:
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_call_state"
        self._attr_native_value = manager.state
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="P4 Doorbell",
        )

    async def async_added_to_hass(self) -> None:
        @callback
        def _on_state(state: str) -> None:
            self._attr_native_value = state
            self.async_write_ha_state()

        self._manager.add_state_listener(_on_state)
