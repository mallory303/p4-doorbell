"""Chime sound selector (library lives in /config/www/p4_doorbell/chimes)."""
from __future__ import annotations

import logging
import os

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    BUNDLED_CHIME_LABEL,
    CHIMES_SUBDIR,
    DOMAIN,
    SIGNAL_CHIMES_UPDATED,
)

_LOGGER = logging.getLogger(__name__)


def _chime_dir(hass) -> str:
    return hass.config.path("www", *CHIMES_SUBDIR.split("/"))


def _list_chimes(hass) -> list[str]:
    try:
        return sorted(
            f
            for f in os.listdir(_chime_dir(hass))
            if os.path.splitext(f)[1].lower() in (".mp3", ".wav", ".ogg", ".m4a")
        )
    except OSError:
        return []


async def async_setup_entry(hass, entry, async_add_entities):
    await hass.async_add_executor_job(
        lambda: os.makedirs(_chime_dir(hass), exist_ok=True)
    )
    async_add_entities([P4ChimeSelect(entry)])


class P4ChimeSelect(SelectEntity, RestoreEntity):
    """Selected chime = what the manual responder plays on ring."""

    _attr_has_entity_name = True
    _attr_name = "Chime sound"

    def __init__(self, entry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_chime"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="P4 Doorbell"
        )
        self._attr_options = [BUNDLED_CHIME_LABEL]
        self._attr_current_option = BUNDLED_CHIME_LABEL

    async def async_added_to_hass(self) -> None:
        if last := await self.async_get_last_state():
            if last.state and last.state not in ("unknown", "unavailable"):
                self._attr_current_option = last.state
        await self._async_refresh()
        self._sync_data()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CHIMES_UPDATED, self._async_refresh
            )
        )

    async def _async_refresh(self) -> None:
        files = await self.hass.async_add_executor_job(_list_chimes, self.hass)
        self._attr_options = [BUNDLED_CHIME_LABEL] + files
        if self._attr_current_option not in self._attr_options:
            self._attr_current_option = BUNDLED_CHIME_LABEL
        if self.hass and self.platform:
            self.async_write_ha_state()

    def _sync_data(self) -> None:
        data = self.hass.data[DOMAIN].get(self._entry.entry_id)
        if data is not None:
            data["chime"] = (
                None
                if self._attr_current_option == BUNDLED_CHIME_LABEL
                else self._attr_current_option
            )

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self._sync_data()
        self.async_write_ha_state()
