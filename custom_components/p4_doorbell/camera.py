"""Live camera entity: streams the P4's RTSP via go2rtc/WebRTC.

HA automatically routes any camera with a stream_source() through go2rtc,
so this works locally AND remotely (Nabu Casa relays the WebRTC) with zero
transcoding on the Pi.
"""
from __future__ import annotations

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    StreamType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_P4_HOST, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([P4DoorbellCamera(entry)])


class P4DoorbellCamera(Camera):
    """rtsp://<p4>:554/live — H.264 passthrough, remuxed to WebRTC by go2rtc."""

    _attr_has_entity_name = True
    _attr_name = "Camera"
    # declares "this camera streams": the dialog shows live view (WebRTC via
    # go2rtc, HLS fallback) instead of just a still preview
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_frontend_stream_type = StreamType.HLS

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__()
        self._attr_unique_id = f"{entry.entry_id}_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="P4 Doorbell"
        )
        host = entry.data[CONF_P4_HOST]
        ip = host.split("://", 1)[-1].split(":", 1)[0].strip("/")
        self._rtsp_url = f"rtsp://{ip}:554/live"

    async def stream_source(self) -> str:
        return self._rtsp_url
