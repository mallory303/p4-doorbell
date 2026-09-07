"""P4 Doorbell integration.

Receives ring/presence events from the ESP32-P4 doorbell (HTTP webhook,
unauthenticated LAN POST /api/webhook/<id>), drives a call state machine with
modular responders, and exposes entities + services + a Lovelace card.
"""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import webhook
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import P4Api
from .call_manager import CallManager
from .const import (
    AVAILABLE_RESPONDERS,
    CARD_URL_PATH,
    CONF_P4_HOST,
    CONF_RESPONDERS,
    DOMAIN,
    SERVICE_ANSWER,
    SERVICE_END_CALL,
    SERVICE_SIMULATE_RING,
)
from .responders.answering_machine import AnsweringMachineResponder
from .responders.llm_guest import LlmGuestResponder
from .responders.manual import ManualResponder

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["event", "binary_sensor", "button", "number"]

RESPONDER_CLASSES = {
    "manual": ManualResponder,
    "answering_machine": AnsweringMachineResponder,
    "llm_guest": LlmGuestResponder,
}


async def _handle_webhook(hass: HomeAssistant, webhook_id: str, request) -> None:
    """POST from the P4: {"event": "ring"|"presence"|"presence_clear"}."""
    manager: CallManager | None = None
    for data in hass.data.get(DOMAIN, {}).values():
        if data.get("webhook_id") == webhook_id:
            manager = data["manager"]
            break
    if manager is None:
        _LOGGER.warning("webhook %s: no matching config entry", webhook_id)
        return
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - tolerate empty/non-JSON bodies as a ring
        payload = {"event": "ring"}
    kind = payload.get("event", "ring")
    if kind == "ring":
        await manager.async_ring(source=payload.get("source", "button"))
    elif kind in ("presence", "presence_clear"):
        await manager.async_presence(kind == "presence")
    else:
        _LOGGER.warning("unknown doorbell event: %s", kind)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    www = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/p4_doorbell_static", str(www), cache_headers=False)]
    )
    add_extra_js_url(hass, CARD_URL_PATH)
    # add as a Lovelace resource too (storage-mode dashboards)
    lovelace = hass.data.get("lovelace")
    if lovelace is not None and getattr(lovelace, "mode", None) == "storage":
        try:
            resources = lovelace.resources
            await resources.async_load()
            if not any(CARD_URL_PATH in r.get("url", "") for r in resources.async_items()):
                await resources.async_create(
                    {"res_type": "module", "url": CARD_URL_PATH}
                )
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "could not auto-register Lovelace resource; add %s manually (module)",
                CARD_URL_PATH,
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    api = P4Api(async_get_clientsession(hass), entry.data[CONF_P4_HOST])
    manager = CallManager(hass, entry.data)

    for name in entry.data.get(CONF_RESPONDERS, ["manual"]):
        cls = RESPONDER_CLASSES.get(name)
        if cls:
            manager.register_responder(cls(hass, entry.data))
        else:
            _LOGGER.warning("unknown responder module: %s", name)

    webhook_id = f"{DOMAIN}_{entry.entry_id}"
    webhook.async_register(
        hass, DOMAIN, "P4 Doorbell", webhook_id, _handle_webhook,
        allowed_methods=("POST",),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "manager": manager,
        "webhook_id": webhook_id,
    }

    await _async_register_frontend(hass)

    if not hass.services.has_service(DOMAIN, SERVICE_ANSWER):
        async def _answer(call):
            for data in hass.data[DOMAIN].values():
                await data["manager"].async_answer()

        async def _end(call):
            for data in hass.data[DOMAIN].values():
                await data["manager"].async_end()

        async def _simulate(call):
            for data in hass.data[DOMAIN].values():
                await data["manager"].async_ring(source="simulate")

        hass.services.async_register(DOMAIN, SERVICE_ANSWER, _answer)
        hass.services.async_register(DOMAIN, SERVICE_END_CALL, _end)
        hass.services.async_register(DOMAIN, SERVICE_SIMULATE_RING, _simulate)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info(
        "P4 doorbell ready. Point the firmware at: POST %s/api/webhook/%s",
        entry.data[CONF_P4_HOST],
        webhook_id,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data:
        webhook.async_unregister(hass, data["webhook_id"])
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
