"""Ring event entity (EventDeviceClass.DOORBELL)."""
from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, EVENT_PRESENCE, EVENT_RING


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([P4RingEventEntity(entry)])


class P4RingEventEntity(EventEntity):
    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["ring", "presence"]
    _attr_has_entity_name = True
    _attr_name = "Ring"

    def __init__(self, entry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_ring"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="P4 Doorbell",
            manufacturer="Olimex/custom",
            model="ESP32-P4 doorbell",
        )

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_RING, self._on_ring)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_PRESENCE, self._on_presence)
        )

    def _on_ring(self, event) -> None:
        self._trigger_event("ring", dict(event.data))
        self.async_write_ha_state()

    def _on_presence(self, event) -> None:
        self._trigger_event("presence", dict(event.data))
        self.async_write_ha_state()
