"""Thin async client for the ESP32-P4 doorbell REST API."""
from __future__ import annotations

import aiohttp


class P4Api:
    """Talks to the P4 firmware endpoints (cam_server.c)."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self._host = host.rstrip("/")

    async def async_get_version(self) -> dict:
        async with self._session.get(
            f"{self._host}/api/version", timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def async_chime(self) -> None:
        async with self._session.post(
            f"{self._host}/api/chime", timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            resp.raise_for_status()

    async def async_play_pcm(self, pcm: bytes) -> None:
        """POST raw PCM16@16kHz mono to /api/play (doorbell speaker)."""
        async with self._session.post(
            f"{self._host}/api/play",
            data=pcm,
            headers={"Content-Type": "application/octet-stream"},
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            resp.raise_for_status()

    async def async_get_volume(self) -> int:
        async with self._session.get(
            f"{self._host}/api/volume", timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            resp.raise_for_status()
            return int((await resp.json())["volume"])

    async def async_set_volume(self, pct: int) -> None:
        async with self._session.post(
            f"{self._host}/api/volume",
            json={"volume": int(pct)},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            resp.raise_for_status()

    async def async_set_ha_webhook(self, url: str) -> None:
        """Push the HA webhook URL to the P4 (it POSTs ring events back)."""
        async with self._session.post(
            f"{self._host}/api/ha",
            json={"url": url},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            resp.raise_for_status()

    @property
    def ui_url(self) -> str:
        """The P4's own web UI (live H.264 player + mic meter + controls)."""
        return f"{self._host}/"
