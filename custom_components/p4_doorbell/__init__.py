"""P4 Doorbell integration.

Receives ring/presence events from the ESP32-P4 doorbell (HTTP webhook,
unauthenticated LAN POST /api/webhook/<id>), drives a call state machine with
modular responders, and exposes entities + services + a Lovelace card.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components import webhook
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import P4Api
from .announce import async_announce as _async_announce
from .call_manager import CallManager
from .const import (
    AVAILABLE_RESPONDERS,
    CARD_URL_PATH,
    CONF_CHIME_PLAYERS,
    CONF_P4_HOST,
    CONF_RESPONDERS,
    CONF_TTS_ENTITY,
    DEFAULT_TTS_ENTITY,
    DOMAIN,
    SERVICE_ANSWER,
    SERVICE_END_CALL,
    SERVICE_SIMULATE_RING,
)
from .responders.answering_machine import AnsweringMachineResponder
from .responders.llm_guest import LlmGuestResponder
from .responders.manual import ManualResponder

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["event", "binary_sensor", "button", "number", "camera", "select", "text"]

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


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Sidebar admin panel (chime library, announce) + API views."""
    from homeassistant.components.frontend import async_register_built_in_panel

    from .views import (
        P4DoorbellChimesView,
        P4DoorbellConfigView,
        P4DoorbellUploadView,
    )

    hass.http.register_view(P4DoorbellChimesView())
    hass.http.register_view(P4DoorbellUploadView())
    hass.http.register_view(P4DoorbellConfigView())
    async_register_built_in_panel(
        hass,
        "iframe",
        sidebar_title="P4 Doorbell",
        sidebar_icon="mdi:doorbell-video",
        frontend_url_path="p4_doorbell",
        config={"url": "/p4_doorbell_static/panel.html"},
    )


async def _async_register_frontend(hass: HomeAssistant) -> None:
    www = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/p4_doorbell_static", str(www), cache_headers=False)]
    )
    # Serve the card from /local (= /config/www): core-served from the very
    # first HTTP request, so a tablet reloading mid-startup can't 404 it
    # (custom static paths register later -> "Configuration error" popups).
    # Content-hash cache-buster so card updates bust WebView caches.
    def _copy_card() -> str:
        src = www / "p4-doorbell-card.js"
        target = Path(hass.config.path("www")) / "p4-doorbell-card.js"
        data = src.read_bytes()
        if not target.exists() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return hashlib.md5(data).hexdigest()[:8]

    card_hash = await hass.async_add_executor_job(_copy_card)
    card_url = f"/local/p4-doorbell-card.js?v={card_hash}"
    add_extra_js_url(hass, card_url)

    async def _register_resource() -> None:
        """Add the card as a Lovelace resource (storage-mode dashboards)."""
        lovelace = hass.data.get("lovelace")
        if lovelace is None:
            _LOGGER.warning("lovelace not ready; card resource not registered")
            return
        try:
            resources = lovelace.resources
            await resources.async_load()
            for r in list(resources.async_items()):
                url = r.get("url", "")
                if "p4-doorbell-card.js" in url and not url.startswith(card_url):
                    try:
                        await resources.async_delete_item(r["id"])
                        _LOGGER.info("removed stale Lovelace resource %s", url)
                    except Exception:
                        _LOGGER.exception("could not remove stale resource %s", url)
            if not any(
                r.get("url", "").startswith(card_url) for r in resources.async_items()
            ):
                await resources.async_create({"res_type": "module", "url": card_url})
                _LOGGER.info("registered Lovelace resource %s", card_url)
        except Exception:
            _LOGGER.exception(
                "could not auto-register Lovelace resource; add %s manually (module)",
                card_url,
            )

    if hass.data.get("lovelace") is not None:
        await _register_resource()
    # Always also retry post-start: if lovelace was ready but its resource
    # collection wasn't, the first attempt may fail - the guard inside
    # _register_resource makes the retry a no-op when it succeeded.
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED,
        lambda _: hass.async_create_task(_register_resource()),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    api = P4Api(async_get_clientsession(hass), entry.data[CONF_P4_HOST])
    manager = CallManager(hass, entry.data)

    responder_data = dict(entry.data)
    responder_data["_entry_id"] = entry.entry_id
    for name in entry.data.get(CONF_RESPONDERS, ["manual"]):
        cls = RESPONDER_CLASSES.get(name)
        if cls:
            manager.register_responder(cls(hass, responder_data))
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
    await _async_register_panel(hass)

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

        async def _announce(call):
            for data in hass.data[DOMAIN].values():
                await _async_announce(hass, entry, data, call)

        hass.services.async_register(DOMAIN, SERVICE_ANSWER, _answer)
        hass.services.async_register(DOMAIN, SERVICE_END_CALL, _end)
        hass.services.async_register(DOMAIN, SERVICE_SIMULATE_RING, _simulate)
        hass.services.async_register(DOMAIN, "announce", _announce)

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
