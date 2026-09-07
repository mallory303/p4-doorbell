"""Config flow for P4 Doorbell."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import P4Api
from .const import (
    AVAILABLE_RESPONDERS,
    CONF_CHIME_PLAYERS,
    CONF_P4_HOST,
    CONF_POPUP_BROWSER,
    CONF_RESPONDERS,
    CONF_TTS_ENTITY,
    DEFAULT_TTS_ENTITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class P4DoorbellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            api = P4Api(
                async_get_clientsession(self.hass), user_input[CONF_P4_HOST]
            )
            try:
                version = await api.async_get_version()
                await self.async_set_unique_id(
                    f"{DOMAIN}_{version.get('project', 'p4')}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"P4 Doorbell ({version.get('built', '?')})",
                    data=user_input,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("cannot reach P4 doorbell")
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_P4_HOST, default="http://192.168.86.185"): str,
                vol.Optional(CONF_CHIME_PLAYERS, default=[]): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="media_player", multiple=True
                    )
                ),
                vol.Optional(CONF_POPUP_BROWSER, default=""): str,
                vol.Optional(
                    CONF_TTS_ENTITY, default=DEFAULT_TTS_ENTITY
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="tts")
                ),
                vol.Optional(CONF_RESPONDERS, default=["manual"]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=AVAILABLE_RESPONDERS, multiple=True, mode="list"
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
