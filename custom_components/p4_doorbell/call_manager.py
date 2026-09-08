"""Call state machine + modular responder registry.

A "call" starts on a ring (button or radar presence), ends on answer-timeout,
hang-up, or a responder finishing. Responder modules plug into the registry;
each gets lifecycle callbacks. Current modules:

  manual            - chime on media players, popup on the wall tablet
  answering_machine - (stub) play a canned TTS message if unanswered
  llm_guest         - (stub) LLM conversation when nobody is home

New modules: subclass Responder, set `name`, add to RESPONDERS.
"""
from __future__ import annotations

import logging
from typing import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    EVENT_ANSWERED,
    EVENT_ENDED,
    EVENT_PRESENCE,
    EVENT_RING,
    STATE_IDLE,
    STATE_RINGING,
)

_LOGGER = logging.getLogger(__name__)

RING_TIMEOUT_S = 45  # unanswered ring auto-ends; the state machine must never wedge


class CallManager:
    """Owns the doorbell call state and dispatches to responder modules."""

    def __init__(self, hass: HomeAssistant, entry_data: dict) -> None:
        self.hass = hass
        self.entry_data = entry_data
        self.state = STATE_IDLE
        self.responders: list = []
        self._state_listeners: list[Callable] = []
        self._ring_timeout_cancel: Callable | None = None

    # -- wiring ---------------------------------------------------------

    def register_responder(self, responder) -> None:
        self.responders.append(responder)
        _LOGGER.debug("responder registered: %s", responder.name)

    def add_state_listener(self, cb: Callable) -> None:
        self._state_listeners.append(cb)

    def _cancel_ring_timeout(self) -> None:
        if self._ring_timeout_cancel:
            self._ring_timeout_cancel()
            self._ring_timeout_cancel = None

    def _set_state(self, state: str) -> None:
        self.state = state
        for cb in self._state_listeners:
            cb(state)

    # -- events from the doorbell ----------------------------------------

    async def async_ring(self, source: str = "button") -> None:
        """Button pressed (or presence-triggered ring)."""
        _LOGGER.info("doorbell ring (%s)", source)
        self.hass.bus.async_fire(EVENT_RING, {"source": source})
        if self.state != STATE_IDLE:
            if source == "radar":
                return  # presence flapping must not tea...[truncated]
        self._set_state(STATE_RINGING)
        self._ring_timeout_cancel = async_call_later(
            self.hass, RING_TIMEOUT_S, self._async_ring_timeout
        )
        for r in self.responders:
            try:
                await r.on_ring(self)
            except Exception:  # noqa: BLE001 - one bad module must not kill a ring
                _LOGGER.exception("responder %s failed on_ring", r.name)

    @callback
    def _async_ring_timeout(self, _now) -> None:
        if self.state == STATE_RINGING:
            _LOGGER.info("ring unanswered for %ds, auto-ending", RING_TIMEOUT_S)
            self.hass.async_create_task(self.async_end())

    async def async_presence(self, present: bool) -> None:
        self.hass.bus.async_fire(EVENT_PRESENCE, {"present": present})

    # -- actions from the UI / services -----------------------------------

    async def async_answer(self) -> None:
        from .const import STATE_ANSWERED  # avoid cycle

        _LOGGER.info("call answered")
        self._cancel_ring_timeout()
        self._set_state(STATE_ANSWERED)
        self.hass.bus.async_fire(EVENT_ANSWERED, {})
        for r in self.responders:
            try:
                await r.on_answered(self)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("responder %s failed on_answered", r.name)

    async def async_end(self) -> None:
        _LOGGER.info("call ended")
        self._cancel_ring_timeout()
        self._set_state(STATE_IDLE)
        self.hass.bus.async_fire(EVENT_ENDED, {})
        for r in self.responders:
            try:
                await r.on_ended(self)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("responder %s failed on_ended", r.name)
