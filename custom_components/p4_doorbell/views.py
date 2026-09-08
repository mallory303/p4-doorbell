"""HTTP views for the doorbell admin panel (chime library management)."""
from __future__ import annotations

import logging
import os
import re

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CHIMES_SUBDIR, CONF_CHIME_PLAYERS, CONF_TTS_ENTITY, DOMAIN, SIGNAL_CHIMES_UPDATED

_LOGGER = logging.getLogger(__name__)

MAX_CHIME_BYTES = 8 * 1024 * 1024
_ALLOWED_EXT = (".mp3", ".wav", ".ogg", ".m4a")


def _chime_dir(hass) -> str:
    return hass.config.path("www", *CHIMES_SUBDIR.split("/"))


def _sanitize(filename: str) -> str:
    name = os.path.basename(filename)
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(". ")
    return name or "chime"


class P4DoorbellChimesView(HomeAssistantView):
    """GET: list chime files."""

    url = "/api/p4_doorbell/chimes"
    name = "api:p4_doorbell:chimes"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        try:
            files = sorted(
                f
                for f in os.listdir(_chime_dir(hass))
                if os.path.splitext(f)[1].lower() in _ALLOWED_EXT
            )
        except OSError:
            files = []
        return self.json({"chimes": files})


class P4DoorbellUploadView(HomeAssistantView):
    """POST multipart: upload a chime file into the library."""

    url = "/api/p4_doorbell/upload_chime"
    name = "api:p4_doorbell:upload_chime"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        data = await request.post()
        upload = data.get("file")
        if upload is None or not getattr(upload, "filename", None):
            return self.json_message("no file field", status_code=400)
        filename = _sanitize(upload.filename)
        if os.path.splitext(filename)[1].lower() not in _ALLOWED_EXT:
            return self.json_message(
                f"unsupported type; use {', '.join(_ALLOWED_EXT)}", status_code=400
            )
        content = upload.file.read()
        if len(content) > MAX_CHIME_BYTES:
            return self.json_message("file too large (8 MB max)", status_code=400)
        target = os.path.join(_chime_dir(hass), filename)

        def _write() -> None:
            os.makedirs(_chime_dir(hass), exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(content)

        await hass.async_add_executor_job(_write)
        _LOGGER.info("chime uploaded: %s (%d bytes)", filename, len(content))
        async_dispatcher_send(hass, SIGNAL_CHIMES_UPDATED)
        return self.json({"ok": True, "file": filename})


class P4DoorbellConfigView(HomeAssistantView):
    """GET: config bits the panel needs (tts entity, chime players)."""

    url = "/api/p4_doorbell/config"
    name = "api:p4_doorbell:config"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return self.json_message("not configured", status_code=404)
        entry = entries[0]
        return self.json(
            {
                "tts_entity": entry.data.get(CONF_TTS_ENTITY, "tts.elevenlabs"),
                "chime_players": entry.data.get(CONF_CHIME_PLAYERS, []),
            }
        )
