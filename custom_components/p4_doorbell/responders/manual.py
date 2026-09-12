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
from homeassistant.helpers.event import async_call_later

from homeassistant.helpers import entity_registry as er

from ..const import (
    CHIME_URL_PATH,
    CONF_CHIME_NOTIFY,
    CONF_CHIME_PLAYERS,
    CONF_CHIME_VOLUME,
    CONF_NOTIFY_TARGETS,
    CONF_P4_HOST,
    CONF_POPUP_BROWSER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _popup_card(hass, entry_data: dict) -> dict:
    """Popup content built from CORE Lovelace cards only.

    The wall tablet (ThinkSmart) runs an old WebView where custom card
    elements are fragile (startup races, cache, parse issues) - a popup
    built from built-in cards always renders.
    """
    cards = []
    cam_id = er.async_get(hass).async_get_entity_id(
        "camera", DOMAIN, f"{entry_data.get('_entry_id')}_camera"
    )
    if cam_id:
        cards.append(
            {
                "type": "picture-entity",
                "entity": cam_id,
                "camera_view": "live",  # WebRTC via go2rtc: works over Nabu Casa
                "show_name": False,
                "show_state": False,
            }
        )
    cards.append(
        {
            "type": "grid",
            "columns": 2,
            "square": False,
            "cards": [
                {
                    "type": "button",
                    "name": "Answer",
                    "icon": "mdi:phone",
                    "tap_action": {
                        "action": "call-service",
                        "service": "p4_doorbell.answer",
                    },
                },
                {
                    "type": "button",
                    "name": "End call",
                    "icon": "mdi:phone-hangup",
                    "tap_action": {
                        "action": "call-service",
                        "service": "p4_doorbell.end_call",
                    },
                },
            ],
        }
    )
    # talkback: iframe mic page - starts the tablet mic on Answer and streams
    # PCM16@16k straight to the doorbell's /api/play speaker input
    p4_host = (entry_data.get(CONF_P4_HOST) or "").rstrip("/")
    if p4_host:
        cards.append(
            {
                "type": "iframe",
                "url": f"/p4_doorbell_static/talkback_v051.html?p4={p4_host}",
                "aspect_ratio": "12%",
            }
        )
    return {"type": "vertical-stack", "cards": cards}


class ManualResponder:
    name = "manual"

    def __init__(self, hass, entry_data) -> None:
        self.hass = hass
        self.entry_data = entry_data

    async def _chime_on_player(self, player: str, chime_url: str, chime_vol) -> None:
        """Play the chime at the configured volume, then restore the player's
        previous volume (a chime shouldn't leave the living room blaring)."""
        prev_state = self.hass.states.get(player)
        prev_vol = (
            prev_state.attributes.get("volume_level")
            if prev_state is not None
            else None
        )
        if chime_vol is not None:
            await self.hass.services.async_call(
                MP_DOMAIN,
                "volume_set",
                {"entity_id": player, "volume_level": float(chime_vol) / 100},
                blocking=False,
            )
        await self.hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                "entity_id": player,
                ATTR_MEDIA_CONTENT_TYPE: "music",
                ATTR_MEDIA_CONTENT_ID: chime_url,
            },
            blocking=True,
        )
        if chime_vol is not None and prev_vol is not None:

            async def _restore(_now, p=player, v=prev_vol) -> None:
                await self.hass.services.async_call(
                    MP_DOMAIN,
                    "volume_set",
                    {"entity_id": p, "volume_level": v},
                    blocking=False,
                )

            async_call_later(self.hass, 20, _restore)

    def _chime_url(self) -> str:
        """Selected chime from the library, else the bundled ding-dong."""
        entry_id = self.entry_data.get("_entry_id", "")
        data = self.hass.data.get(DOMAIN, {}).get(entry_id) or {}
        if chime := data.get("chime"):
            from urllib.parse import quote

            return "/local/p4_doorbell/chimes/" + quote(chime)
        return CHIME_URL_PATH

    async def on_ring(self, call) -> None:
        players = self.entry_data.get(CONF_CHIME_PLAYERS) or []
        notify_chime = self.entry_data.get(CONF_CHIME_NOTIFY) or []
        if not notify_chime:
            # fall back to the push targets: the same companion devices can
            # play the chime via command_media - one less thing to configure
            notify_chime = list(self.entry_data.get(CONF_NOTIFY_TARGETS) or [])
            if notify_chime:
                _LOGGER.info("chime: no dedicated chime targets; reusing notify targets %s",
                             notify_chime)
        chime_url = get_url(self.hass) + self._chime_url()
        chime_vol = self.entry_data.get(CONF_CHIME_VOLUME)
        if players or notify_chime:
            for player in players:
                try:
                    await self._chime_on_player(player, chime_url, chime_vol)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.exception("chime failed on %s", player)
                    await self.hass.services.async_call(
                        PN_DOMAIN,
                        "create",
                        {
                            "title": "P4 Doorbell: chime failed",
                            "message": (
                                f"`{player}` rejected playback ({err}). Pick a "
                                "player that supports *Play media* - the "
                                "companion-app media player on tablets cannot "
                                "receive audio; use a speaker/display or the "
                                "browser_mod browser player."
                            ),
                            "notification_id": "p4_doorbell_chime_fail",
                        },
                        blocking=False,
                    )

        # chime via companion TTS: the ThinkSmart's media player is dead
        # (media_session unavailable; command_media falls back to showing a
        # raw notification) but its TTS pipeline WORKS (same path as
        # voice-assist answers) - so the hub announces the ring aloud.
        for target in notify_chime:
            slug = target.split(".", 1)[-1]  # notify.lenovo_x -> lenovo_x
            service = f"mobile_app_{slug}"
            if not self.hass.services.has_service("notify", service):
                _LOGGER.warning(
                    "chime: no legacy notify service notify.%s for %s - skipped",
                    service,
                    target,
                )
                continue
            try:
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {
                        "message": "TTS",
                        "title": "P4 Doorbell",
                        "data": {"tts_text": "Ding dong. Someone is at the door."},
                    },
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("chime TTS command failed on %s", target)

        # sound-carrier notification: the ThinkSmart's media playback is dead
        # but its NOTIFICATION stream is audible - so the chime rides a
        # dedicated notification channel. The user assigns the chime mp3 to
        # the "p4_doorbell_chime" channel once in Android settings
        # (Settings -> Apps -> Home Assistant -> Notifications -> channel ->
        # Sound); from then on every ring plays the ding-dong.
        for target in notify_chime:
            slug = target.split(".", 1)[-1]
            service = f"mobile_app_{slug}"
            if not self.hass.services.has_service("notify", service):
                continue
            try:
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {
                        "title": "🚪 Doorbell",
                        "message": "Someone is at the door.",
                        "data": {
                            "channel": "p4_doorbell_chime",
                            "importance": "high",
                            "tag": "p4_doorbell_ring",
                        },
                    },
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("ring notification failed on %s", target)

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

        # mobile push notifications removed per user request - popup is the
        # sole ring alert on the hub; phone/watch get their own alerts via
        # automations if desired.

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
        # close the tablet popup too, otherwise it lingers and blocks re-popup
        browser_id = (self.entry_data.get(CONF_POPUP_BROWSER) or "").strip()
        if browser_id and self.hass.services.has_service("browser_mod", "close_popup"):
            try:
                await self.hass.services.async_call(
                    "browser_mod",
                    "close_popup",
                    {"browser_id": browser_id},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("browser_mod close_popup failed")
