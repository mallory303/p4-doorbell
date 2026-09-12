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

        def _list() -> list[str]:
            try:
                return sorted(
                    f
                    for f in os.listdir(_chime_dir(hass))
                    if os.path.splitext(f)[1].lower() in _ALLOWED_EXT
                )
            except OSError:
                return []

        files = await hass.async_add_executor_job(_list)
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


    async def delete(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        body = await request.post()
        name = _sanitize(str(body.get("file", "")))
        if not name:
            return self.json_message("bad filename", status_code=400)
        removed = {"removed": False}

        def _rm() -> None:
            path = os.path.join(_chime_dir(hass), name)
            if os.path.isfile(path):
                os.remove(path)
                removed["removed"] = True

        await hass.async_add_executor_job(_rm)
        async_dispatcher_send(hass, SIGNAL_CHIMES_UPDATED)
        return self.json(removed)


class P4DoorbellToMediaView(HomeAssistantView):
    """POST {"file": name}: copy a chime into HA's media folder (/media/p4_doorbell).

    The media folder is browsable by every media player via Media Source, so
    the chime becomes playable anywhere without custom URLs. file="bundled"
    copies the built-in ding-dong.
    """

    url = "/api/p4_doorbell/to_media"
    name = "api:p4_doorbell:to_media"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        name = _sanitize(str(body.get("file", "")))
        if not name:
            return self.json_message("bad filename", status_code=400)

        if name.lower() == "bundled":
            from pathlib import Path

            src = str(Path(__file__).parent / "www" / "chime.mp3")
            name = "ding-dong.mp3"
        else:
            if os.path.splitext(name)[1].lower() not in _ALLOWED_EXT:
                return self.json_message("unsupported type", status_code=400)
            src = os.path.join(_chime_dir(hass), name)
        if not os.path.isfile(src):
            return self.json_message("no such chime", status_code=404)

        result: dict = {}

        def _copy() -> None:
            media_root = hass.config.media_dirs.get("media") or hass.config.path("media")
            dest_dir = os.path.join(media_root, "p4_doorbell")
            os.makedirs(dest_dir, exist_ok=True)
            import shutil

            dest = os.path.join(dest_dir, name)
            shutil.copyfile(src, dest)
            result["media_source"] = f"media-source://media_source/local/p4_doorbell/{name}"

        try:
            await hass.async_add_executor_job(_copy)
        except OSError as exc:
            return self.json_message(f"copy failed: {exc}", status_code=500)
        _LOGGER.info("chime copied to media folder: %s", result["media_source"])
        return self.json({"ok": True, **result})


class P4DoorbellTalkbackView(HomeAssistantView):
    """POST raw PCM16 chunk -> forward to the doorbell speaker (/api/play).

    Same-origin for the popup iframe: dodges WebView mixed-content and
    private-network-access blocking, and works over Nabu Casa too.
    """

    url = "/api/p4_doorbell/talkback"
    name = "api:p4_doorbell:talkback"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        chunk = await request.read()
        if not chunk or len(chunk) > 2 * 1024 * 1024:
            return self.json_message("bad chunk", status_code=400)
        for data in hass.data.get(DOMAIN, {}).values():
            api = data.get("api")
            if api is not None:
                try:
                    await api.async_play_pcm(chunk)
                except Exception as exc:  # noqa: BLE001
                    return self.json_message(f"p4 forward failed: {exc}", status_code=502)
                return self.json({"ok": True, "bytes": len(chunk)})
        return self.json_message("no doorbell configured", status_code=503)


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
