"""Manual responder: chime the house, pop the doorbell UI up on the tablet.

On ring:
  1. play the bundled chime on every configured media_player
  2. open the fullscreen doorbell popup on the wall tablet via browser_mod
     (gracefully skipped when browser_mod or a browser id is absent)
  3. always fire a persistent notification as a last-resort path
"""
from __future__ import annotations

import logging

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.persistent_notification import (
    DOMAIN as PN_DOMAIN,
)
from homeassistant.helpers.network import get_url

from homeassistant.helpers import entity_registry as er

from ..const import (
    CHIME_URL_PATH,
    CONF_CHIME_PLAYERS,
    CONF_NOTIFY_TARGETS,
    CONF_P4_HOST,
    CONF_POPUP_BROWSER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _popup_card(hass, entry_data: dict) -> dict:
    card = {
        "type": "custom:p4-doorbell-card",
        "fullscreen": True,
        "p4_host": entry_data.get(CONF_P4_HOST),
    }
    cam_id = er.async_get(hass).async_get_entity_id(
        "camera", DOMAIN, f"{entry_data.get('_entry_id')}_camera"
    )
    if cam_id:
        card["camera_entity"] = cam_id   # WebRTC via go2rtc: works over Nabu Casa
    return card


class ManualResponder:
    name = "manual"

    def __init__(self, hass, entry_data) -> None:
        self.hass = hass
        self.entry_data = entry_data

    async def on_ring(self, call) -> None:
        players = self.entry_data.get(CONF_CHIME_PLAYERS) or []
        if players:
            chime_url = get_url(self.hass) + CHIME_URL_PATH
            for player in players:
                try:
                    await self.hass.services.async_call(
                        MP_DOMAIN,
                        SERVICE_PLAY_MEDIA,
                        {
                            "entity_id": player,
                            ATTR_MEDIA_CONTENT_TYPE: "music",
                            ATTR_MEDIA_CONTENT_ID: chime_url,
                        },
                        blocking=False,
                    )
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("chime failed on %s", player)

        browser_id = (self.entry_data.get(CONF_POPUP_BROWSER) or "").strip()
        if browser_id and self.hass.services.has_service("browser_mod", "popup"):
            try:
                await self.hass.services.async_call(
                    "browser_mod",
                    "popup",
                    {
                        "browser_id": browser_id,
                        "title": "Doorbell",
                        "content": _popup_card(self.hass, self.entry_data),
                        "size": "fullscreen",
                        "dismissable": True,
                    },
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("browser_mod popup failed")
        elif browser_id:
            _LOGGER.warning("browser_mod not installed - popup skipped")

        # mobile push (companion app on phone/tablet; mirrors to the watch)
        for target in self.entry_data.get(CONF_NOTIFY_TARGETS) or []:
            try:
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {
                        "entity_id": target,
                        "title": "🚪 Doorbell",
                        "message": "Someone is at the door.",
                    },
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("push notification failed on %s", target)

        # last-resort visibility path, always on
        await self.hass.services.async_call(
            PN_DOMAIN,
            "create",
            {
                "title": "Doorbell",
                "message": "Someone is at the door.",
                "notification_id": "p4_doorbell_ring",
            },
            blocking=False,
        )

    async def on_ended(self, call) -> None:
        await self.hass.services.async_call(
            PN_DOMAIN,
            "dismiss",
            {"notification_id": "p4_doorbell_ring"},
            blocking=False,
        )
