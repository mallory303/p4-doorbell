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
    CONF_CHIME_NOTIFY,
    CONF_CHIME_PLAYERS,
    CONF_NOTIFY_TARGETS,
    CONF_P4_HOST,
    CONF_POPUP_BROWSER,
    CONF_RESPONDERS,
    CONF_TTS_ENTITY,
    DEFAULT_TTS_ENTITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "http://192.168.86.185"


def _schema(defaults: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_P4_HOST, default=defaults.get(CONF_P4_HOST, DEFAULT_HOST)
            ): str,
            vol.Optional(
                CONF_CHIME_PLAYERS, default=defaults.get(CONF_CHIME_PLAYERS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player", multiple=True)
            ),
            vol.Optional(
                CONF_POPUP_BROWSER, default=defaults.get(CONF_POPUP_BROWSER, "")
            ): str,
            vol.Optional(
                CONF_NOTIFY_TARGETS, default=defaults.get(CONF_NOTIFY_TARGETS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="notify", multiple=True)
            ),
            vol.Optional(
                CONF_CHIME_NOTIFY, default=defaults.get(CONF_CHIME_NOTIFY, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="notify", multiple=True)
            ),
            vol.Optional(
                CONF_TTS_ENTITY,
                default=defaults.get(CONF_TTS_ENTITY, DEFAULT_TTS_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="tts")),
            vol.Optional(
                CONF_RESPONDERS, default=defaults.get(CONF_RESPONDERS, ["manual"])
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=AVAILABLE_RESPONDERS, multiple=True, mode="list"
                )
            ),
        }
    )


async def _validate(hass, host: str) -> dict:
    """Probe /api/version; raises on any failure."""
    api = P4Api(async_get_clientsession(hass), host)
    return await api.async_get_version()


class P4DoorbellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                version = await _validate(self.hass, user_input[CONF_P4_HOST])
                return self.async_create_entry(
                    title=f"P4 Doorbell ({version.get('built', '?')})",
                    data=user_input,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("cannot reach P4 doorbell")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            try:
                await _validate(self.hass, user_input[CONF_P4_HOST])
                return self.async_update_reload_and_abort(entry, data=user_input)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("cannot reach P4 doorbell")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(user_input or dict(entry.data)),
            errors=errors,
        )
