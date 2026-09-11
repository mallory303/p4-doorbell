"""Announce: synthesize the message and speak it (house + doorbell speaker)."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant, ServiceCall

from .api import P4Api
from .const import (
    CONF_CHIME_PLAYERS,
    CONF_TTS_ENTITY,
    DEFAULT_ANNOUNCE_MESSAGE,
    DEFAULT_TTS_ENTITY,
)

_LOGGER = logging.getLogger(__name__)


async def async_announce(hass: HomeAssistant, entry, data: dict, call: ServiceCall) -> None:
    """House announce via tts.speak + visitor announce on the doorbell."""
    message = (call.data.get("message") or "").strip()
    if not message:
        message = data.get("announce_message") or DEFAULT_ANNOUNCE_MESSAGE
    tts_entity = entry.data.get(CONF_TTS_ENTITY, DEFAULT_TTS_ENTITY)
    players = entry.data.get(CONF_CHIME_PLAYERS, [])

    if players:
        # native path: HA streams TTS audio straight to the players
        await hass.services.async_call(
            "tts",
            "speak",
            {
                "entity_id": tts_entity,
                "media_player_entity_id": players,
                "message": message,
            },
            blocking=False,
        )

    api: P4Api | None = data.get("api")
    if api:
        hass.async_create_task(_visitor_announce(hass, api, message, tts_entity))


async def _visitor_announce(hass: HomeAssistant, api: P4Api, message: str, tts_entity: str) -> None:
    """Synthesize -> transcode to PCM16@16k -> stream to the P4 speaker."""
    try:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        from homeassistant.helpers.network import get_url

        session = async_get_clientsession(hass)
        base = get_url(hass, allow_internal=True, prefer_external=False)
        # version-proof: use the public REST endpoint instead of tts internals
        async with session.post(
            f"{base}/api/tts_get_url",
            json={"platform": tts_entity, "message": message},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        url = data.get("url") or data.get("path")
        if not url:
            raise RuntimeError(f"tts_get_url returned no url: {data}")
        if url.startswith("/"):
            url = base + url
        async with session.get(url) as resp:
            resp.raise_for_status()
            audio_bytes = await resp.read()
        if not audio_bytes:
            raise RuntimeError("TTS returned no audio")
    except Exception:
        _LOGGER.exception("visitor announce: TTS synthesis failed")
        return

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-v", "error", "-i", "pipe:0",
            "-f", "s16le", "-ar", "16000", "-ac", "1", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        pcm, err = await proc.communicate(audio_bytes)
        if proc.returncode != 0 or not pcm:
            raise RuntimeError(f"ffmpeg rc={proc.returncode} {err[:200]!r}")
    except Exception:
        _LOGGER.exception("visitor announce: transcode failed (ffmpeg on HA host?)")
        return

    try:
        await api.async_play_pcm(pcm)
        _LOGGER.info("visitor announce played on doorbell (%d PCM bytes)", len(pcm))
    except Exception:
        _LOGGER.exception("visitor announce: doorbell playback failed")
