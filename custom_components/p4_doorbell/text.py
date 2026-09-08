"""Announce message text entity (synthesized with ElevenLabs on announce)."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_ANNOUNCE_MESSAGE, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([P4AnnounceText(entry)])


class P4AnnounceText(TextEntity, RestoreEntity):
    """The message spoken to the visitor / house on p4_doorbell.announce."""

    _attr_has_entity_name = True
    _attr_name = "Announce message"
    _attr_native_max = 200
    _attr_icon = "mdi:account-voice"

    def __init__(self, entry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_announce_message"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="P4 Doorbell"
        )
        self._attr_native_value = DEFAULT_ANNOUNCE_MESSAGE

    async def async_added_to_hass(self) -> None:
        if last := await self.async_get_last_state():
            if last.state and last.state not in ("unknown", "unavailable"):
                self._attr_native_value = last.state
        self._sync_data()

    def _sync_data(self) -> None:
        data = self.hass.data[DOMAIN].get(self._entry.entry_id)
        if data is not None:
            data["announce_message"] = self._attr_native_value

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self._sync_data()
        self.async_write_ha_state()
