"""Responder module interface + registry."""
from __future__ import annotations

from homeassistant.core import HomeAssistant


class Responder:
    """Base class for doorbell call responder modules.

    A responder decides what happens while a call is RINGING (or after it is
    answered). Modules run in the order they were enabled in the config flow.
    """

    name = "base"

    def __init__(self, hass: HomeAssistant, entry_data: dict) -> None:
        self.hass = hass
        self.entry_data = entry_data

    async def on_ring(self, call) -> None:
        """A ring just started (call.state == 'ringing')."""

    async def on_answered(self, call) -> None:
        """A human answered from the popup."""

    async def on_ended(self, call) -> None:
        """Call ended / timed out / hung up."""
